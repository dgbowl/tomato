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
from collections import defaultdict
from datetime import datetime, timezone
from threading import current_thread
from pathlib import Path
from typing import Union, TypeVar

import zmq
import psutil

from tomato.driverinterface_1_0 import ModelInterface as MI_1_0
from tomato.driverinterface_2_0 import ModelInterface as MI_2_0
from tomato.driverinterface_2_1 import ModelInterface as MI_2_1
from tomato.drivers import driver_to_interface
from tomato.models import Reply, Daemon

logger = logging.getLogger(__name__)
ModelInterface = TypeVar("ModelInterface", MI_1_0, MI_2_0, MI_2_1)
IDLE_MEASUREMENT_INTERVAL = None
MAX_REGISTER_RETRIES = 3


def tomato_driver_bootstrap(
    req: zmq.Socket, logger: logging.Logger, interface: ModelInterface, driver: str
):
    logger.debug("getting daemon status")
    req.send_pyobj(dict(cmd="status"))
    daemon: Daemon = req.recv_pyobj().data

    logger.info("registering components for driver '%s'", driver)
    for comp in daemon.cmps.values():
        if comp.driver == driver:
            key = (comp.address, comp.channel)
            if key in interface.devmap:
                logger.debug(
                    "component %s already registered, skipping",
                    comp.name,
                )
                continue
            elif interface.retries.get(key, 0) == MAX_REGISTER_RETRIES:
                logger.warning(
                    "component %s has exceeded MAX_REGISTER_RETRIES, skipping",
                    comp.name,
                )
                continue
            logger.info("registering component %s", comp.name)
            ret = interface.dev_register(address=comp.address, channel=comp.channel)
            if ret.success:
                logger.debug("registered component %s: %s", comp.name, ret.msg)
            else:
                logger.critical(
                    "failed to register component %s: %s", comp.name, ret.msg
                )
            params = dict(name=comp.name, capabilities=ret.data)
            req.send_pyobj(dict(cmd="component", params=params))
            ret = req.recv_pyobj()
    logger.info("driver '%s' bootstrapped successfully", driver)


def perform_idle_measurements(
    interface: ModelInterface, t_last: Union[float, None]
) -> Union[float, None]:
    if not hasattr(interface, "cmp_measure"):
        return t_last

    if "idle_measurement_interval" in interface.settings:
        imi = interface.settings["idle_measurement_interval"]
    elif hasattr(interface, "idle_measurement_interval"):
        imi = interface.idle_measurement_interval
    else:
        imi = IDLE_MEASUREMENT_INTERVAL
    if imi is None:
        return None

    t_now = time.perf_counter()
    if t_last is not None and t_now - t_last < imi:
        return t_last
    for key in interface.devmap.keys():
        interface.cmp_measure(key=key)
    return t_now

def kill_tomato_driver(pid: int):
    """
    Wrapper around :func:`psutil.terminate`.

    Here we kill the (grand)children of the process with the name of `tomato-job`,
    i.e. the individual task functions. This allows the `tomato-job` process to exit
    gracefully once the task functions join.

    Note that on Windows, the `tomato-job.exe` process has two children: a `python.exe`
    which is the actual process running the job, and `conhost.exe`, which we want to
    avoid killing.

    """
    proc = psutil.Process(pid)
    to_kill = proc.children()
    to_kill.append(proc)
    logger.warning(f"killing process {proc.name()!r} with pid {proc.pid}")
    proc.terminate()
    gone, alive = psutil.wait_procs([to_kill], timeout=1)
    logger.debug(f"{gone=}")
    logger.debug(f"{alive=}")
    return gone

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
        pid = os.getpid()
        thispid = os.getpid()
        thisproc = psutil.Process(thispid)
        for p in thisproc.parents():
            if p.name() == "tomato-driver.exe":
                pid = p.pid
                break
    elif psutil.POSIX:
        pid = os.getpid()

    logger.info("attempting to create Interface for driver '%s'", args.driver)
    Interface = driver_to_interface(args.driver)
    if Interface is None:
        logger.critical("class DriverInterface driver '%s' not found", args.driver)
        return

    logger.debug("getting daemon status")
    req.send_pyobj(dict(cmd="status"))
    daemon: Daemon = req.recv_pyobj().data
    drv = daemon.drvs[args.driver]
    try:
        interface: ModelInterface = Interface(settings=drv.settings)
    except Exception as e:
        logger.critical(
            "could not instantiate driver '%s': %s", args.driver, e, exc_info=True
        )
        raise RuntimeError("could not instantiate driver '%s'") from e

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
    t_last = None
    try:
        while True:
            socks = dict(poller.poll(100))
            if rep in socks:
                msg = rep.recv_pyobj()
                logger.debug("received msg=%s", msg)
                if "cmd" not in msg:
                    logger.error(f"received msg without cmd: {msg=}")
                    ret = Reply(success=False, msg="received msg without cmd", data=msg)
                elif msg["cmd"] == "register":
                    tomato_driver_bootstrap(req, logger, interface, args.driver)
                    if any([retry for retry in interface.retries.values()]):
                        ret = Reply(
                            success=False,
                            msg="some components not registered successfully",
                            data=interface.retries,
                        )
                    else:
                        ret = Reply(
                            success=True,
                            msg="all components re-registered successfully",
                            data=interface.retries,
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
                elif msg["cmd"] == "cmp_register":
                    ret = interface.cmp_register(**msg["params"])
                    cname = f"{args.driver}:({msg['params']['address']},{msg['params']['channel']})"
                    if ret.success:
                        params = dict(name=cname, capabilities=ret.data)
                        req.send_pyobj(dict(cmd="component", params=params))
                        ret = req.recv_pyobj()
                elif hasattr(interface, msg["cmd"]):
                    try:
                        ret = getattr(interface, msg["cmd"])(**msg["params"])
                    except (ValueError, AttributeError) as e:
                        logger.info("above error caught by driver process")
                        ret = Reply(
                            success=False,
                            msg=f"{type(e)}: {str(e)}",
                            data=None,
                        )
                else:
                    logger.critical("unknown command: '%s'", msg["cmd"])
                    ret = Reply(
                        success=False,
                        msg=f"unknown command: {msg['cmd']}",
                        data=None,
                    )
                logger.debug("replying %s", ret)
                rep.send_pyobj(ret)
            if status == "stop":
                break
            elif status == "running":
                try:
                    t_last = perform_idle_measurements(interface, t_last)
                except (RuntimeError, ValueError, AttributeError):
                    logger.info("above error caught by driver process")
    except Exception as e:
        logger.critical("uncaught exception %s", type(e), exc_info=True)
        raise e

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
    driver_retries = defaultdict(int)
    component_retries = defaultdict(int)

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
                if drv.pid is not None and (
                    not psutil.pid_exists(drv.pid)
                    or psutil.Process(drv.pid).status() in psutil.STATUS_ZOMBIE
                ):
                    # this happens when a fully-registered driver has crashed
                    logger.warning("respawning crashed driver '%s'", driver)
                    spawn_tomato_driver(*args)
                    spawned_drivers[driver] = 1
                elif drv.pid is None and drv.spawned_at is None:
                    # this happens when spawn_tomato_driver crashed for some reason
                    # as drv.spawned_at is set in spawn_tomato_driver
                    retry = driver_retries[driver]
                    if retry < MAX_REGISTER_RETRIES:
                        logger.info("spawning driver '%s' (retry %d)", driver, retry)
                        spawn_tomato_driver(*args)
                        driver_retries[driver] += 1
                    elif retry == MAX_REGISTER_RETRIES:
                        logger.warning(
                            "driver '%s' reached maximum spawn retries, check config",
                            driver,
                        )
                        driver_retries[driver] += 1
                    spawned_drivers[driver] = 1
                elif drv.pid is None and drv.connected_at is None:
                    # this happens when tomato-driver was launched but did not
                    # report to tomato-daemon for some reason
                    retry = driver_retries[driver]
                    if retry < MAX_REGISTER_RETRIES:
                        logger.info("spawning driver '%s' (retry %d)", driver, retry)
                        spawn_tomato_driver(*args)
                        driver_retries[driver] += 1
                    elif retry == MAX_REGISTER_RETRIES:
                        logger.warning(
                            "driver '%s' reached maximum spawn retries, see driver log",
                            driver,
                        )
                        driver_retries[driver] += 1
                    spawned_drivers[driver] = 1
                elif driver in spawned_drivers:
                    logger.info("driver '%s' spawned with pid %d", driver, drv.pid)
                    spawned_drivers.pop(driver)
            elif driver in spawned_drivers:
                spawned_drivers[driver] += 1

        if len(spawned_drivers) == 0:
            contact_drivers = set()
            for comp in daemon.cmps.values():
                if comp.capabilities is None:
                    key = (comp.address, comp.channel)
                    if component_retries[key] < MAX_REGISTER_RETRIES:
                        contact_drivers.add(comp.driver)
            for driver in contact_drivers:
                drv = daemon.drvs[driver]
                if drv.port is None:
                    continue
                logger.info("contacting driver '%s' to re-register components", driver)
                dreq = context.socket(zmq.REQ)
                dreq.connect(f"tcp://127.0.0.1:{drv.port}")
                dreq.send_pyobj(dict(cmd="register", params=None, sender=sender))
                ret = dreq.recv_pyobj()
                component_retries = ret.data
                dreq.close()
        time.sleep(1 if len(spawned_drivers) > 0 else 0.1)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", sender=sender))
    daemon = req.recv_pyobj().data
    for driver in daemon.drvs.values():
        if driver.pid is None:
            logger.info(
                "stopping driver '%s' - no action (no pid)",
                driver.name,
            )
            continue
        elif driver.port is None:
            logger.info(
                "stopping driver '%s' - killing pid %d",
                driver.name,
                driver.pid,
            )
            gone = kill_tomato_driver(driver.pid)
            if driver.pid in gone:
                ret = Reply(success=True)
        else:
            logger.info(
                "stopping driver '%s' - sending 'stop' command on port %s",
                driver.name,
                driver.port,
            )
            ret = stop_tomato_driver(driver.port, context)
            if ret.success:
                params = dict(driver=driver.name, port=None)
                req.send_pyobj(dict(cmd="driver", params=params))
                ret = req.recv_pyobj()

        if ret.success:
            logger.info("stopped driver '%s'", driver.name)
        else:
            logger.warning("could not stop driver '%s'", driver.name)
