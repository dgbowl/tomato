import os
import subprocess
import logging
import time
import argparse
from importlib import metadata
from datetime import datetime, timezone
from threading import currentThread

import zmq
import psutil

import tomato.drivers
from tomato.models import Reply

logger = logging.getLogger(__name__)


def tomato_driver() -> None:
    # ARGUMENT PARSING
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

    # LOGFILE
    logfile = f"drivers_{args.port}.log"
    logger = logging.getLogger(f"{__name__}.tomato_drivers({args.driver!r})")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logfile, mode="a"), logging.StreamHandler()],
    )

    # PORTS
    context = zmq.Context()
    rep = context.socket(zmq.REP)
    port = rep.bind_to_random_port("tcp://127.0.0.1")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{args.port}")

    logger.debug("getting pid")
    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()

    logger.debug("getting daemon status")
    req.send_pyobj(
        dict(cmd="status", with_data=True, sender=f"{__name__}.tomato_driver_bootstrap")
    )
    daemon = req.recv_pyobj().data
    logger.debug(f"{daemon=}")

    logger.info(f"attempting to spawn driver {args.driver!r}")
    if not hasattr(tomato.drivers, args.driver):
        logger.critical(f"library of driver {args.driver!r} not found")
        return

    kwargs = dict(settings=daemon.drvs[args.driver].settings)
    driver = getattr(tomato.drivers, args.driver).Driver(**kwargs)

    logger.info(f"registering devices in driver {args.driver!r}")
    for dev in daemon.devs.values():
        if dev.driver == args.driver:
            for channel in dev.channels:
                driver.dev_register(address=dev.address, channel=channel)
    logger.debug(f"{driver.devmap=}")

    logger.info(f"driver {args.driver!r} bootstrapped successfully")

    params = dict(
        name=args.driver,
        port=port,
        pid=pid,
        connected_at=str(datetime.now(timezone.utc)),
        settings=driver.settings,
    )
    try:
        req.send_pyobj(
            dict(cmd="driver", params=params, sender=f"{__name__}.tomato_driver")
        )
        ret = req.recv_pyobj()
    except:
        import sys
        logger.critical(f"{sys.exc_info()=}")
    if not ret.success:
        logger.error(f"could not push driver {args.driver!r} state to tomato-daemon")
        logger.debug(f"{ret=}")
        return

    logger.info(f"driver {args.driver!r} is entering main loop")

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
                    msg=f"status of driver {params['name']!r} is {status!r}",
                    data=dict(**params, status=status),
                )
            elif msg["cmd"] == "stop":
                status = "stop"
                ret = Reply(
                    success=True,
                    msg=f"stopping driver {args.driver!r}",
                    data=dict(status=status, driver=args.driver),
                )
            elif msg["cmd"] == "settings":
                driver.settings = msg["params"]
                params["settings"] = driver.settings
                ret = Reply(
                    success=True,
                    msg="settings received",
                    data=msg.get("params"),
                )
            elif msg["cmd"] == "dev_register":
                driver.dev_register(**msg["params"])
                ret = Reply(
                    success=True,
                    msg="device registered",
                    data=msg.get("params"),
                )
            elif msg["cmd"] == "task_status":
                ret = driver.task_status(**msg["params"])
            elif msg["cmd"] == "task_start":
                ret = driver.task_start(**msg["params"])
            elif msg["cmd"] == "task_data":
                ret = driver.task_data(**msg["params"])
            logger.debug(f"{ret=}")
            rep.send_pyobj(ret)
        if status == "stop":
            break

    logger.info(f"driver {args.driver!r} is beginning teardown")

    driver.teardown()

    logger.critical(f"driver {args.driver!r} is quitting")


def spawn_tomato_driver(port: int, driver: str, req):
    cmd = ["tomato-driver", "--port", str(port), driver]
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NO_WINDOW
        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)
    params = dict(name=driver, spawned_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(
        dict(
            cmd="driver",
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
        elif to > timeout:
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
        time.sleep(timeout / 1e3)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
    daemon = req.recv_pyobj().data
    for driver in daemon.drvs.values():
        logger.debug(f"stopping driver {driver.name!r} on port {driver.port}")
        ret = stop_tomato_driver(driver.port, context)
        logger.debug(f"{ret=}")
        if ret.success:
            logger.info(f"stopped driver {driver.name!r}")
        else:
            logger.warning(f"could not stop driver {driver.name!r}")
