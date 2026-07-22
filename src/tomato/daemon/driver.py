"""
**tomato.daemon.driver**: the driver manager of tomato daemon
-------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import argparse
import logging
import subprocess
import time
from collections import defaultdict
from importlib import metadata
from pathlib import Path
from threading import current_thread
from typing import Union

import psutil
import zmq

import tomato.utils
from tomato.daemon import lpp
from tomato.drivers import ModelInterface, driver_to_interface
from tomato.models import Daemon, Reply, SpawnData

logger = logging.getLogger(__name__)
IDLE_MEASUREMENT_INTERVAL = None
MAX_REGISTER_RETRIES = 3

SPAWN_RETRIES = 3
SPAWN_DELAY = 5.0
HEARTBEAT = 5.0


def tomato_driver_bootstrap(
    req: zmq.Socket, logger: logging.Logger, interface: ModelInterface, driver: str
):
    logger.debug("getting daemon status")
    req.send_pyobj(dict(cmd="status"))
    daemon: Daemon = req.recv_pyobj().data

    logger.info("registering components for driver '%s'", driver)
    for comp in daemon.devicefile.components.values():
        if comp.driver == driver:
            key = (comp.address, comp.channel)
            if key in interface.devmap:
                logger.debug(
                    "component %s already registered, skipping",
                    comp.name,
                )
                continue
            elif (
                hasattr(interface, "retries")
                and interface.retries.get(key, 0) == MAX_REGISTER_RETRIES
            ):
                logger.warning(
                    "component %s has exceeded MAX_REGISTER_RETRIES, skipping",
                    comp.name,
                )
                continue
            logger.info("registering component %s", comp.name)
            ret = interface.cmp_register(address=comp.address, channel=comp.channel)
            if ret.success:
                logger.debug("registered component %s: %s", comp.name, ret.msg)
            else:
                logger.critical(
                    "failed to register component %s: %s", comp.name, ret.msg
                )
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


def driver_heartbeat(
    req: zmq.Socket, params: dict, HEARTBEAT: float = HEARTBEAT
) -> Reply | None:
    tN = time.perf_counter()
    if tN - params["heartbeat_time"] > HEARTBEAT:
        sender = f"{__name__}.driver_heartbeat"
        logger = logging.getLogger(sender)
        logger.critical("heartbeating driver '%s'", params["name"])
        params["heartbeat_time"] = tN
        req.send_pyobj(dict(cmd="driver_set", params=params, sender=sender))
        ret = req.recv_pyobj()
        if ret.success:
            logger.debug("heartbeat of driver '%s' successful", params["name"])
        else:
            logger.warning("heartbeat of driver '%s' failed", params["name"])


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
    logfile = f"tomato_daemon_{args.port}_driver_{args.driver}.log"
    logpath = Path(args.logdir) / logfile
    logger = logging.getLogger(f"{__name__}.tomato_driver")
    logging.basicConfig(
        level=args.verbosity,
        format="%(asctime)s - %(levelname)8s - %(name)-40s - %(message)s",
        handlers=[logging.FileHandler(logpath, mode="a")],
    )

    # PORTS
    context = zmq.Context()
    rep = context.socket(zmq.REP)
    port = rep.bind_to_random_port("tcp://127.0.0.1")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{args.port}")

    logger.info("attempting to create Interface for driver '%s'", args.driver)
    Interface = driver_to_interface(args.driver)
    if Interface is None:
        logger.critical("class DriverInterface driver '%s' not found", args.driver)
        return

    logger.debug("getting daemon status")
    req.send_pyobj(dict(cmd="status"))
    daemon: Daemon = req.recv_pyobj().data
    settings = daemon.devicefile.drivers[args.driver].settings
    try:
        interface = Interface(settings=settings)  # ty: ignore[call-non-callable]
    except Exception as e:
        logger.critical(
            "could not instantiate driver '%s': %s", args.driver, e, exc_info=True
        )
        raise RuntimeError("could not instantiate driver '%s'") from e

    hb_pars = {
        "name": args.driver,
        "port": port,
        "version": Interface.version,
        "pid": tomato.utils.get_pid(),
        "heartbeat_time": 0,
    }
    ret = driver_heartbeat(req, hb_pars)
    if ret is not None and not ret.success:
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
                        # ret = getattr(interface, msg["cmd"])(**msg["params"])
                        ret = getattr(interface, msg["cmd"])(**msg.get("params", {}))
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
                    driver_heartbeat(req, hb_pars)
    except Exception as e:
        logger.critical("uncaught exception %s", type(e), exc_info=True)
        raise e

    logger.info("driver '%s' is beginning to quit", args.driver)
    interface.quit()

    logger.info("driver '%s' is quitting", args.driver)


def stop_tomato_driver(port: int, context) -> Reply:
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
    lppargs = dict(
        endpoint=f"tcp://127.0.0.1:{port}",
        context=context,
        sender=sender,
        timeout=timeout,
    )

    component_retries = defaultdict(int)

    while getattr(thread, "do_run"):
        spawned_drivers = set()
        spawned_components = set()
        msg = dict(cmd="status", sender=sender)
        ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
        if req.closed:
            setattr(thread, "do_run", False)
            break
        if ret.success and ret.data is not None:
            daemon: Daemon = ret.data
        else:
            logger.critical(ret.msg)
            setattr(thread, "do_run", False)
            break

        for n, d in daemon.drivers.items():
            tN = time.perf_counter()
            if n not in daemon.devicefile.drivers:
                if d.port is not None:
                    logger.warning("%s: stopping driver", n)
                    ret = stop_tomato_driver(d.port, context)
                    if not ret.success:
                        logger.warning("%s: failed to stop driver: %s", n, ret.msg)
                req.send_pyobj(dict(cmd="driver_del", params={"name": n}))
                ret = req.recv_pyobj()
                logger.warning("%s: removed driver", n)
            elif d.port is not None:
                if (tN - d.heartbeat_time > HEARTBEAT) or (
                    d.heartbeat_time == 0 and tN - d.spawn_time > SPAWN_DELAY
                ):
                    try:
                        logger.debug("%s: checking driver on port %d", n, d.port)
                        dreq = context.socket(zmq.REQ)
                        dreq.RCVTIMEO = 1000
                        dreq.connect(f"tcp://127.0.0.1:{d.port}")
                        dreq.send_pyobj(dict(cmd="status"))
                        ret = dreq.recv_pyobj()
                        if ret.success and len(ret.data) == 0:
                            logger.info("%s: registering components", n)
                            dreq.send_pyobj(dict(cmd="register", sender=sender))
                            ret = dreq.recv_pyobj()
                            if ret.success:
                                logger.info("%s: component registration successful", n)
                            else:
                                logger.warning(
                                    "%s: component registration failed: %s", n, ret
                                )
                        params = {"name": d.name, "heartbeat_time": tN}
                        d.heartbeat_time = tN
                    except zmq.error.Again:
                        logger.warning("%s: check of driver failed, resetting", n)
                        params = vars(SpawnData(name=d.name))
                    except Exception as e:
                        logger.critical(e)
                        raise e
                    req.send_pyobj(dict(cmd="driver_set", params=params))
                    ret = req.recv_pyobj()
            elif tN - d.spawn_time > SPAWN_DELAY and d.spawn_count < SPAWN_RETRIES:
                logger.info("%s: spawning driver: retry %d", n, d.spawn_count)
                cmd = [
                    "tomato-driver",
                    "--port",
                    f"{daemon.port}",
                    "--verbosity",
                    f"{daemon.verbosity}",
                    "--logdir",
                    daemon.settings["logdir"],
                    n,
                ]
                if psutil.WINDOWS:
                    cfs = subprocess.CREATE_NO_WINDOW
                    cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                    subprocess.Popen(cmd, creationflags=cfs)
                elif psutil.POSIX:
                    subprocess.Popen(cmd, start_new_session=True)
                logger.info("%s: driver process launched", n)
                params = {
                    "name": n,
                    "spawn_time": tN,
                    "spawn_count": d.spawn_count + 1,
                }
                req.send_pyobj(dict(cmd="driver_set", params=params))
                ret = req.recv_pyobj()
                spawned_drivers.add(d.name)

        time.sleep(1 if len(spawned_drivers) > 0 else 0.1)

    logger.info("instructed to quit")
    req.send_pyobj(dict(cmd="status", sender=sender))
    daemon = req.recv_pyobj().data
    for driver in daemon.drivers.values():
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
            logger.info("stopped driver '%s'", driver.name)
        else:
            logger.warning("could not stop driver '%s'", driver.name)
