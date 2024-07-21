"""
**tomato.daemon.driver**: the driver manager of tomato daemon
-------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

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

from tomato.driverinterface_1_0 import ModelInterface
from tomato.drivers import driver_to_interface
from tomato.models import Reply

logger = logging.getLogger(__name__)


def tomato_driver() -> None:
    """
    The function called when `tomato-driver` is executed.

    This function is responsible for managing all activities involving devices of a
    single driver type.

    First, the list of devices (and their channel/address) for the specified driver is
    fetched from the `tomato-daemon`. Then, a new instance of the specified driver is
    spawned, populating its device map using the above list. If successful, the current
    process information is fed back to the `tomato-daemon`.

    Afterwards, the main loop handles all requests related to each of the devices
    managed by this driver process, including job commands. Finally, if the driver is
    instructed to stop, it attempts to perform a teardown before exiting.
    """
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
        "--verbosity",
        help="Verbosity of the tomato-driver.",
        default=logging.DEBUG,
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
        level=args.verbosity,
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logfile, mode="a")],
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
    Interface = driver_to_interface(args.driver)
    if Interface is None:
        logger.critical(f"library of driver {args.driver!r} not found")
        return
    drv = daemon.drvs[args.driver]
    interface: ModelInterface = Interface(settings=drv.settings)

    logger.info("registering devices in driver '%s'", args.driver)
    for dev in daemon.devs.values():
        if dev.driver == args.driver:
            for channel in dev.channels:
                ret = interface.dev_register(address=dev.address, channel=channel)
                logger.debug(f"iface  {ret=}")
                name = "/".join((args.driver, dev.address, str(channel)))
                req.send_pyobj(
                    dict(
                        cmd="component", params={"name": name, "capabilities": ret.data}
                    )
                )
                ret = req.recv_pyobj()
                logger.debug(f"daemon {ret=}")
    logger.debug(f"{interface.devmap=}")

    logger.info("driver '%s' bootstrapped successfully", args.driver)

    params = dict(
        name=args.driver,
        port=port,
        pid=pid,
        connected_at=str(datetime.now(timezone.utc)),
        settings=interface.settings,
    )
    req.send_pyobj(
        dict(cmd="driver", params=params, sender=f"{__name__}.tomato_driver")
    )
    ret = req.recv_pyobj()
    if not ret.success:
        logger.error(f"could not push driver {args.driver!r} state to tomato-daemon")
        logger.debug(f"{ret=}")
        return

    logger.info("driver '%s' is entering main loop", args.driver)

    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)
    status = "running"
    while True:
        socks = dict(poller.poll(100))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug("received msg=%s", msg)
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
                interface.settings = msg["params"]
                params["settings"] = interface.settings
                ret = Reply(
                    success=True,
                    msg="settings received",
                    data=msg.get("params"),
                )
            elif hasattr(interface, msg["cmd"]):
                ret = getattr(interface, msg["cmd"])(**msg["params"])
            else:
                logger.critical("unknown command: '%s'", msg["cmd"])
            logger.debug("replying %s", ret)
            rep.send_pyobj(ret)
        if status == "stop":
            break

    logger.info(f"driver {args.driver!r} is beginning reset")

    interface.reset()

    logger.critical(f"driver {args.driver!r} is quitting")


def spawn_tomato_driver(port: int, driver: str, req: zmq.Socket, verbosity: int):
    # cmd = ["tomato-driver", "--port", str(port), "--verbosity", str(verbosity), driver]
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
    """
    The driver manager thread of `tomato-daemon`.

    This manager ensures individual driver processes are (re-)spawned and instructed to
    quit as necessary.
    """

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
        action_counter = 0
        for driver in daemon.drvs.keys():
            if driver not in daemon.drvs:
                logger.debug("spawning driver '%s'", driver)
                spawn_tomato_driver(daemon.port, driver, req, daemon.verbosity)
                action_counter += 1
            else:
                drv = daemon.drvs[driver]
                if drv.pid is not None and not psutil.pid_exists(drv.pid):
                    logger.warning(f"respawning crashed driver {driver!r}")
                    spawn_tomato_driver(daemon.port, driver, req, daemon.verbosity)
                    action_counter += 1
                elif drv.pid is None and drv.spawned_at is None:
                    logger.debug(f"spawning driver {driver!r}")
                    spawn_tomato_driver(daemon.port, driver, req, daemon.verbosity)
                    action_counter += 1
                elif drv.pid is None:
                    tspawn = datetime.fromisoformat(drv.spawned_at)
                    if (datetime.now(timezone.utc) - tspawn).seconds > 10:
                        logger.warning(f"respawning late driver {driver!r}")
                        spawn_tomato_driver(daemon.port, driver, req, daemon.verbosity)
                        action_counter += 1
        logger.debug("tick")
        time.sleep(1 if action_counter > 0 else 0.1)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
    daemon = req.recv_pyobj().data
    for driver in daemon.drvs.values():
        logger.debug("stopping driver '%s' on port %d", driver.name, driver.port)
        ret = stop_tomato_driver(driver.port, context)
        if ret.success:
            logger.info("stopped driver '%s'", driver.name)
        else:
            logger.warning("could not stop driver '%s'", driver.name)
