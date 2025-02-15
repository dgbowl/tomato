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
from threading import current_thread
from pathlib import Path
from typing import Union

import zmq
import psutil

from tomato.driverinterface_1_0 import ModelInterface as MI_1_0
from tomato.driverinterface_2_0 import ModelInterface as MI_2_0
from tomato.drivers import driver_to_interface
from tomato.models import Reply

logger = logging.getLogger(__name__)
ModelInterface = Union[MI_1_0, MI_2_0]


def tomato_driver_bootstrap(
    req: zmq.Socket, logger: logging.Logger, interface: ModelInterface, driver: str
):
    logger.debug("getting daemon status")
    req.send_pyobj(dict(cmd="status"))
    daemon = req.recv_pyobj().data
    drv = daemon.drvs[driver]
    interface.settings = drv.settings

    logger.info("registering components for driver '%s'", driver)
    for comp in daemon.cmps.values():
        if comp.driver == driver:
            logger.info("registering component %s", (comp.address, comp.channel))
            ret = interface.dev_register(address=comp.address, channel=comp.channel)
            params = dict(name=comp.name, capabilities=ret.data)
            req.send_pyobj(dict(cmd="component", params=params))
            ret = req.recv_pyobj()
    logger.info("driver '%s' bootstrapped successfully", driver)


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
        version=f"%(prog)s version {metadata.version('tomato')}",
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
        "--logdir",
        help="Logging directory for the tomato-driver.",
        default=".",
        type=str,
    )
    parser.add_argument(
        "driver",
        type=str,
        help="Name of the driver module.",
    )
    args = parser.parse_args()

    # LOGFILE
    logfile = f"driver_{args.driver}_{args.port}.log"
    logpath = Path(args.logdir) / logfile
    logger = logging.getLogger(f"{__name__}.tomato_driver({args.driver!r})")
    logging.basicConfig(
        level=args.verbosity,
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logpath, mode="a")],
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

    logger.info("attempting to create Interface for driver '%s'", args.driver)
    Interface = driver_to_interface(args.driver)
    if Interface is None:
        logger.critical("class DriverInterface driver '%s' not found", args.driver)
        return

    interface: ModelInterface = Interface()
    tomato_driver_bootstrap(req, logger, interface, args.driver)

    params = dict(
        name=args.driver,
        port=port,
        pid=pid,
        connected_at=str(datetime.now(timezone.utc)),
        version=interface.version,
        settings=interface.settings,
    )
    req.send_pyobj(
        dict(cmd="driver", params=params, sender=f"{__name__}.tomato_driver")
    )
    ret = req.recv_pyobj()
    if not ret.success:
        logger.error("could not push driver '%s' state to tomato-daemon", args.driver)
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
            elif msg["cmd"] == "register":
                tomato_driver_bootstrap(req, logger, interface, args.driver)
                ret = Reply(
                    success=True,
                    msg="components re-registered successfully",
                    data=interface.devmap.keys(),
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

    logger.info("driver '%s' is beginning reset", args.driver)
    interface.reset()

    logger.info("driver '%s' is quitting", args.driver)


def spawn_tomato_driver(
    port: int, driver: str, req: zmq.Socket, verbosity: int, logpath: str
):
    cmd = [
        "tomato-driver",
        "--port",
        str(port),
        "--verbosity",
        str(verbosity),
        "--logdir",
        str(logpath),
        driver,
    ]
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
        logger.info("driver process for driver '%s' launched", driver)
    else:
        logger.error("could not launch driver process for driver '%s'", driver)


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
    sender = f"{__name__}.manager"
    context = zmq.Context()
    logger = logging.getLogger(sender)
    thread = current_thread()
    logger.info("launched successfully")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    to = timeout

    spawned_drivers = dict()

    while getattr(thread, "do_run"):
        req.send_pyobj(dict(cmd="status", sender=sender))
        events = dict(poller.poll(to))
        if req not in events:
            logger.warning("could not contact tomato-daemon in %d ms", to)
            to = to * 2
            continue
        elif to > timeout:
            to = timeout

        daemon = req.recv_pyobj().data
        for driver in daemon.drvs.keys():
            args = [
                daemon.port,
                driver,
                req,
                daemon.verbosity,
                daemon.settings["logdir"],
            ]
            if driver not in daemon.drvs:
                logger.debug("spawning driver '%s'", driver)
                spawn_tomato_driver(*args)
                spawned_drivers[driver] = 1
            elif driver not in spawned_drivers or spawned_drivers[driver] > 5:
                drv = daemon.drvs[driver]
                if drv.pid is not None and not psutil.pid_exists(drv.pid):
                    logger.warning("respawning crashed driver '%s'", driver)
                    spawn_tomato_driver(*args)
                    spawned_drivers[driver] = 1
                elif drv.pid is None and drv.spawned_at is None:
                    logger.debug("spawning driver '%s'", driver)
                    spawn_tomato_driver(*args)
                    spawned_drivers[driver] = 1
                elif driver in spawned_drivers:
                    logger.info("driver '%s' spawned at pid %d", driver, drv.pid)
                    spawned_drivers.pop(driver)
            elif driver in spawned_drivers:
                spawned_drivers[driver] += 1

        if len(spawned_drivers) == 0:
            contact_drivers = set()
            for comp in daemon.cmps.values():
                if comp.capabilities is None:
                    contact_drivers.add(comp.driver)
            for driver in contact_drivers:
                drv = daemon.drvs[driver]
                if drv.port is None:
                    continue
                logger.debug("contacting driver '%s' to re-register components", driver)
                dreq = context.socket(zmq.REQ)
                dreq.connect(f"tcp://127.0.0.1:{drv.port}")
                dreq.send_pyobj(dict(cmd="register", params=None, sender=sender))
                ret = dreq.recv_pyobj()
                logger.debug(f"{ret=}")
                dreq.close()
        time.sleep(1 if len(spawned_drivers) > 0 else 0.1)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", sender=sender))
    daemon = req.recv_pyobj().data
    for driver in daemon.drvs.values():
        logger.debug("stopping driver '%s' on port %d", driver.name, driver.port)
        ret = stop_tomato_driver(driver.port, context)
        if ret.success:
            logger.info("stopped driver '%s'", driver.name)
        else:
            logger.warning("could not stop driver '%s'", driver.name)
