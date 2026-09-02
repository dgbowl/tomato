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
from importlib import metadata
from pathlib import Path
from threading import current_thread

import psutil
import zmq

import tomato.utils
from tomato.daemon import drvdb
from tomato.drivers import ModelInterface, driver_to_interface
from tomato.models import Daemon, DrvState, Reply
from tomato.utils import context

logger = logging.getLogger(__name__)

IDLE_MEASUREMENT_INTERVAL = None
MAX_REGISTER_RETRIES = 3

SPAWN_RETRIES = 3
SPAWN_DELAY = 5.0
HEARTBEAT = 5.0


def tomato_driver_bootstrap(
    req: zmq.Socket,
    logger: logging.Logger,
    interface: ModelInterface,
    driver: str,
):
    """
    Function that attempts to register all configured components for this driver.

    This helper function is executed when the ``register`` command is set to the driver process. The daemon is first polled for up-to-date configuration, and then each of the returned components is registered, if necessary, using :func:`cmp_register` of the driver interface.

    In case the registration fails, a limited number of retries (as specified by the ``MAX_REGISTER_RETRIES`` constant) can be attempted on subsequent runs of this function.

    """
    logger.debug("getting daemon status")
    req.send_pyobj({"cmd": "status"})
    daemon: Daemon = req.recv_pyobj().data

    logger.info("registering components for driver '%s'", driver)
    for comp in daemon.devicefile.components.values():
        if comp.driver == driver:
            if interface.version in {"2.1", "2.0"}:
                key = (comp.address, comp.channel)
            else:
                key = comp.name
            if key in interface.devmap:
                logger.debug(
                    "component %s already registered, skipping",
                    comp.name,
                )
                continue
            elif (
                hasattr(interface, "retries")
                and interface.retries.get(key, 0) == MAX_REGISTER_RETRIES  # ty: ignore[unresolved-attribute]
            ):
                logger.warning(
                    "component %s has exceeded MAX_REGISTER_RETRIES, skipping",
                    comp.name,
                )
                continue
            logger.info("registering component %s", comp.name)
            ret = interface.cmp_register(
                name=comp.name, address=comp.address, channel=comp.channel
            )
            if ret.success:
                logger.debug("registered component %s: %s", comp.name, ret.msg)
            else:
                logger.critical(
                    "failed to register component %s: %s", comp.name, ret.msg
                )
    logger.info("driver '%s' bootstrapped successfully", driver)


def perform_idle_measurements(
    interface: ModelInterface, t_last: float | None
) -> float | None:
    """
    Function running idle measurements on the driver.

    This function periodically runs the :func:`cmp_measure` on each component on the driver. The interval is determined from driver configuration using the ``"idle_measurement_interval"`` setting, driver defaults using the :obj:`interface.idle_measurement_interval` object, or tomato default (``IDLE_MEASUREMENT_INTERVAL``).

    .. note::

        How idle measurements are handled is up to the individual driver. By default, the :func:`cmp_measure` function will not submit new measurements when a task or a measurement is already running.

    """
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
    for key in interface.devmap:
        if interface.version in {"2.1", "2.0"}:
            interface.cmp_measure(key=key)
        else:
            interface.cmp_measure(name=key)
    return t_now


def stop_tomato_driver(port: int) -> Reply:
    """
    The default mechanism for stopping tomato drivers.

    This function is used by the tomato driver manager to gracefully stop the driver, if an existing driver port is known.
    """
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj({"cmd": "stop", "sender": f"{__name__}.stop_tomato_driver"})
    return req.recv_pyobj()


def kill_tomato_driver(pid: int):
    """
    The backup mechanism for stoping tomato drivers.

    This function is useful if the driver port is unknown or not responsive.

    Wrapper around :func:`psutil.terminate`. Here we kill the (grand)children of the process with the name of `tomato-job`, i.e. the individual task functions. This allows the `tomato-job` process to exit gracefully once the task functions join.

    .. note::

        On Windows, the `tomato-job.exe` process has two children: a `python.exe` process which is the actual process running the job, and `conhost.exe` process, which we want to avoid killing.

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

    This function is responsible for managing all activities involving devices of a single driver type.

    First, the list of devices (and their channel/address) for the specified driver is fetched from the `tomato-daemon`. Then, a new instance of the specified driver is spawned, populating its device map using the above list. The state of the driver is stored .

    Afterwards, the main loop handles all requests related to each of the devices managed by this driver process, including job commands. Finally, if the driver is instructed to stop, it attempts to perform a teardown before exiting.
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
    req.send_pyobj({"cmd": "status"})
    daemon: Daemon = req.recv_pyobj().data
    dbpath = daemon.settings["jobs"]["dbpath"]
    settings = daemon.devicefile.drivers[args.driver].settings
    try:
        interface = Interface(settings=settings)  # ty: ignore[call-non-callable]
    except Exception as e:
        logger.critical(
            "could not instantiate driver '%s': %s", args.driver, e, exc_info=True
        )
        raise RuntimeError("could not instantiate driver '%s'") from e

    params = {
        "port": port,
        "version": Interface.version,
        "pid": tomato.utils.get_pid(),
        "heartbeat_time": 0,
    }
    drv = drvdb.update_drv(name=args.driver, params=params, dbpath=dbpath)
    if drv is None:
        logger.error("could not push driver '%s' state to tomato-daemon", args.driver)
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
                    if any(interface.retries.values()):
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
                        data={"status": status, "driver": args.driver},
                    )
                elif msg["cmd"] == "settings":
                    interface.settings = msg["params"]
                    ret = Reply(
                        success=True,
                        msg="settings received",
                        data=msg.get("params"),
                    )
                elif hasattr(interface, msg["cmd"]):
                    try:
                        ret = getattr(interface, msg["cmd"])(**msg.get("params", {}))
                    except (ValueError, AttributeError) as e:
                        logger.info("above error caught by driver process")
                        ret = Reply(
                            success=False,
                            msg=f"{type(e)}: {e!r}",
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
        raise RuntimeError(str(e))

    logger.info("driver '%s' is beginning to quit", args.driver)
    interface.quit()

    logger.info("driver '%s' is quitting", args.driver)


def manager(timeout: int = 1000):
    """
    The driver manager thread of `tomato-daemon`.

    This manager ensures individual driver processes are (re-)spawned and instructed to quit as necessary. The drivers are periodically checked using the ``HEARTBEAT`` constant as the interval. All changes are stored in the drivers table.
    """
    sender = f"{__name__}.manager"
    logger = logging.getLogger(sender)
    thread = current_thread()
    logger.info("launched successfully")
    req = context.socket(zmq.REQ)
    req.connect("inproc://daemon")

    while getattr(thread, "do_run"):  # noqa:B009
        spawned_drivers = set()
        msg = {"cmd": "status", "sender": sender}
        req.send_pyobj(msg)
        ret = req.recv_pyobj()
        if ret.success and ret.data is not None:
            daemon: Daemon = ret.data
        else:
            logger.critical(ret.msg)
            setattr(thread, "do_run", False)  # noqa:B010
            break

        dbpath = daemon.settings["jobs"]["dbpath"]
        drivers = drvdb.get_drvs_where(where="name IS NOT NULL", dbpath=dbpath)
        for d in drivers:
            tN = time.perf_counter()
            if d.name not in daemon.devicefile.drivers:
                if d.port is not None:
                    logger.warning("%s: stopping driver", d.name)
                    ret = stop_tomato_driver(d.port)
                    if not ret.success:
                        logger.warning("%s: failed to stop driver: %s", d.name, ret.msg)
                ret = drvdb.del_drv(name=d.name, dbpath=dbpath)
                if ret is None:
                    logger.warning("%s: removed driver", d.name)
                else:
                    logger.error("%s: could not delete driver", d.name)
            elif d.port is not None:
                if (tN - d.heartbeat_time > HEARTBEAT) or (
                    d.heartbeat_time == 0 and tN - d.spawn_time > SPAWN_DELAY
                ):
                    try:
                        logger.debug("%s: checking driver on port %d", d.name, d.port)
                        dreq = context.socket(zmq.REQ)
                        dreq.RCVTIMEO = 1000
                        dreq.connect(f"tcp://127.0.0.1:{d.port}")
                        dreq.send_pyobj({"cmd": "status"})
                        ret = dreq.recv_pyobj()
                        if ret.success and len(ret.data) == 0:
                            logger.info("%s: registering components", d.name)
                            dreq.send_pyobj({"cmd": "register", "sender": sender})
                            ret = dreq.recv_pyobj()
                            if ret.success:
                                logger.info(
                                    "%s: component registration successful", d.name
                                )
                            else:
                                logger.warning(
                                    "%s: component registration failed: %s", d.name, ret
                                )
                        params = {"heartbeat_time": tN}
                    except zmq.error.Again:
                        logger.warning("%s: check of driver failed, resetting", d.name)
                        params = vars(DrvState(name=d.name))
                        params.pop("name")
                    except Exception as e:
                        logger.critical("uncaught exception %s", type(e), exc_info=True)
                        raise RuntimeError(str(e))
                    drvdb.update_drv(name=d.name, params=params, dbpath=dbpath)
            elif tN - d.spawn_time > SPAWN_DELAY and d.spawn_count < SPAWN_RETRIES:
                logger.info("%s: spawning driver: retry %d", d.name, d.spawn_count)
                cmd = [
                    "tomato-driver",
                    "--port",
                    f"{daemon.port}",
                    "--verbosity",
                    f"{daemon.verbosity}",
                    "--logdir",
                    daemon.settings["logdir"],
                    d.name,
                ]
                if psutil.WINDOWS:
                    cfs = subprocess.CREATE_NO_WINDOW
                    cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                    subprocess.Popen(cmd, creationflags=cfs)
                elif psutil.POSIX:
                    subprocess.Popen(cmd, start_new_session=True)
                logger.info("%s: driver process launched", d.name)
                params = {
                    "spawn_time": tN,
                    "spawn_count": d.spawn_count + 1,
                }
                drvdb.update_drv(name=d.name, params=params, dbpath=dbpath)
                spawned_drivers.add(d.name)

        time.sleep(1 if len(spawned_drivers) > 0 else 0.1)

    logger.info("instructed to quit")
    req.send_pyobj({"cmd": "status", "sender": sender})
    daemon = req.recv_pyobj().data
    dbpath = daemon.settings["jobs"]["dbpath"]
    drivers = drvdb.get_drvs_where(where="name IS NOT NULL", dbpath=dbpath)
    for d in drivers:
        if d.pid is None:
            logger.info("%s: stopping driver - no action (no pid)", d.name)
            continue
        elif d.port is None:
            logger.info("%s: stopping driver - killing pid %d", d.name, d.pid)
            kill_tomato_driver(d.pid)
        else:
            logger.info("%s: stopping driver - 'stop' on port %d", d.name, d.port)
            stop_tomato_driver(d.port)
