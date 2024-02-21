import os
import subprocess
import logging
import json
import time
import argparse
from importlib import metadata
from datetime import datetime, timezone
from pathlib import Path
from threading import currentThread

import zmq
import psutil

import tomato.drivers
from tomato.models import Pipeline, Daemon, Reply

logger = logging.getLogger(__name__)


def tomato_driver() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "--port",
        help="Port of the tomato-daemon.",
        default=1234,
        type=int,
    )
    parser.add_argument(
        "driver",
        type=str,
        help="Name of the driver module.",
    )
    args = parser.parse_args()

    logfile = f"drivers_{args.port}.log"
    logger = logging.getLogger(f"tomato.drivers.{args.driver}")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logfile, mode="a"), logging.StreamHandler()],
    )

    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()
    logger.debug(f"{pid=}")

    context = zmq.Context()

    rep = context.socket(zmq.REP)
    port = rep.bind_to_random_port("tcp://127.0.0.1")
    logger.debug(f"{port=}")

    logger.debug("getting daemon status")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{args.port}")
    req.send_pyobj(
        dict(cmd="status", with_data=True, sender=f"tomato.drivers.{args.driver}")
    )
    daemon = req.recv_pyobj().data
    logger.debug(f"{daemon=}")

    logger.info(f"attempting to spawn driver {args.driver!r}")
    if hasattr(tomato.drivers, args.driver):
        driver = getattr(tomato.drivers, args.driver).Driver()
        logger.info(f"{driver=}")

    params = dict(pid=pid, port=port, connected_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(
        dict(
            cmd="driver",
            name=args.driver,
            params=params,
            sender=f"tomato.drivers.{args.driver}",
        )
    )
    logger.debug(f"{req.recv_pyobj()=}")
    # time.sleep(10)

    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)
    status = "running"
    while True:
        socks = dict(poller.poll(100))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug(f"received {msg=}")
            if "cmd" not in msg:
                logger.error(f"received msg without cmd: {msg=}")
                ret = Reply(success=False, msg="received msg without cmd", data=msg)
            elif msg["cmd"] == "status":
                ret = Reply(
                    success=True,
                    msg=f"status of driver {args.driver!r} is {status!r}",
                    data=dict(status=status, driver=args.driver),
                )
            elif msg["cmd"] == "stop":
                status = "stop"
                logger.debug("here")
                ret = Reply(
                    success=True,
                    msg=f"stopping driver {args.driver!r}",
                    data=dict(status=status, driver=args.driver),
                )
            elif msg["cmd"] == "settings":
                ret = Reply(
                    success=True,
                    msg=f"settings received",
                    data=msg.get("params"),
                )
            logger.debug(f"{ret=}")
            rep.send_pyobj(ret)
        if status == "stop":
            break
    logger.critical("quitting")


def spawn_tomato_driver(port: int, driver: str, req):
    cmd = ["tomato-driver", "--port", str(port), driver]
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NO_WINDOW
        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)
    params = dict(spawned_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(
        dict(
            cmd="driver",
            name=driver,
            params=params,
            sender=f"{__name__}.spawn_tomato_driver",
        )
    )
    ret = req.recv_pyobj()
    if ret.success:
        logger.info(f"driver {driver!r} started")
    else:
        logger.error(f"could not start {driver!r}")


def stop_tomato_driver(port: int, context):
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="stop", sender=f"{__name__}.stop_tomato_driver"))
    return req.recv_pyobj()


def manager(port: int, timeout: int = 1000):
    context = zmq.Context()
    logger = logging.getLogger(f"{__name__}.manager")
    thread = currentThread()
    logger.info("launched successfully")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    to = timeout

    while getattr(thread, "do_run"):
        req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
        events = dict(poller.poll(to))
        if req not in events:
            logger.warning(f"could not contact tomato-daemon in {to} ms")
            to = to * 2
            continue
        else:
            to = timeout
        daemon = req.recv_pyobj().data
        drivers_needed = {v.driver for v in daemon.devs.values()}
        for driver in drivers_needed:
            if driver not in daemon.drvs:
                logger.debug(f"spawning driver {driver!r}")
                spawn_tomato_driver(daemon.port, driver, req)
            else:
                drv = daemon.drvs[driver]
                if drv.pid is not None and not psutil.pid_exists(drv.pid):
                    logger.warning(f"respawning crashed driver {driver!r}")
                    spawn_tomato_driver(daemon.port, driver, req)
                elif drv.pid is None and drv.spawned_at is None:
                    logger.debug(f"spawning driver {driver!r}")
                    spawn_tomato_driver(daemon.port, driver, req)
                elif drv.pid is None:
                    tspawn = datetime.fromisoformat(drv.spawned_at)
                    if (datetime.now(timezone.utc) - tspawn).seconds > 10:
                        logger.warning(f"respawning late driver {driver!r}")
                        spawn_tomato_driver(daemon.port, driver, req)
        time.sleep(0.1)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
    daemon = req.recv_pyobj().data
    for driver in daemon.drvs.values():
        logger.debug(f"stopping driver {driver.name!r} on port {driver.port}")
        ret = stop_tomato_driver(driver.port, context)
        logger.debug(f"{ret=}")
        if ret.success:
            logger.debug(f"stopped driver {driver.name!r}")
        else:
            logger.warning(f"could not stop driver {driver.name!r}")
