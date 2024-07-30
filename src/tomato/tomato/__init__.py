"""
**tomato.tomato**: command line interface to the tomato daemon
--------------------------------------------------------------
.. codeauthor::
    Peter Kraus

Module of functions to interact with tomato. Includes basic tomato daemon functions:

- :func:`status` to query the status of the tomato daemon
- :func:`start` to start a new tomato daemon
- :func:`stop` to stop a running tomato daemon
- :func:`init` to create a default ``settings.toml`` file
- :func:`reload` to process the ``settings.toml`` and ``devices.yml`` files again

Also includes the following *pipeline* management functions:

- :func:`pipeline_load` to load a sample into a pipeline
- :func:`pipeline_eject` to eject any sample from a pipeline
- :func:`pipeline_ready` to mark a pipeline as ready

"""

import os
import subprocess
import textwrap
import json
from pathlib import Path
from datetime import datetime, timezone
from importlib import metadata

import logging
import psutil
import zmq
import yaml
import toml

from tomato.models import Reply, Pipeline, Device, Driver, Component

logger = logging.getLogger(__name__)
VERSION = metadata.version("tomato")
MAX_RETRIES = 10


def set_loglevel(delta: int):
    loglevel = min(max(30 - (10 * delta), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def load_device_file(yamlpath: Path) -> dict:
    logger.debug("loading device file from '%s'", yamlpath)
    try:
        with yamlpath.open("r") as infile:
            jsdata = yaml.safe_load(infile)
    except FileNotFoundError:
        logger.error("device file not found. Running with default devices.")
        devpath = Path(__file__).parent / ".." / "data" / "default_devices.json"
        with devpath.open() as inp:
            jsdata = json.load(inp)
    return jsdata


def get_pipelines(
    devs: dict[str, Device], pipelines: list
) -> tuple[dict[str, Pipeline], dict[str, Component]]:
    pips = {}
    cmps = {}
    for pip in pipelines:
        if "*" in pip["name"]:
            data = {"name": pip["name"], "devs": {}}
            if len(pip["devices"]) > 1:
                logger.error("more than one component in a wildcard pipeline")
                continue
            for comp in pip["devices"]:
                if comp["device"] not in devs:
                    logger.error("device '%s' not found", comp["device"])
                    break
                dev = devs[comp["device"]]
                for ch in dev.channels:
                    name = pip["name"].replace("*", f"{ch}")
                    h = "/".join((dev.driver, dev.address, str(ch)))
                    c = Component(
                        name=h,
                        driver=dev.driver,
                        device=dev.name,
                        address=dev.address,
                        channel=ch,
                        role=comp["role"],
                    )
                    cmps[h] = c
                    p = Pipeline(name=name, components=[h])
                    pips[p.name] = p
        else:
            data = {"name": pip["name"], "components": []}
            for comp in pip["devices"]:
                if comp["device"] not in devs:
                    logger.error("device '%s' not found", comp["device"])
                    break
                dev = devs[comp["device"]]
                if comp["channel"] not in dev.channels:
                    logger.error(
                        "channel %d not found on device '%s'",
                        comp["channel"],
                        comp["device"],
                    )
                    break
                h = "/".join((dev.driver, dev.address, str(comp["channel"])))
                c = Component(
                    name=h,
                    driver=dev.driver,
                    device=dev.name,
                    address=dev.address,
                    channel=comp["channel"],
                    role=comp["role"],
                )
                data["components"].append(h)
                cmps[h] = c
            pips[data["name"]] = Pipeline(**data)
    return pips, cmps


def _updater(context, port, cmd, params):
    dreq = context.socket(zmq.REQ)
    dreq.connect(f"tcp://127.0.0.1:{port}")
    dreq.send_pyobj(dict(cmd=cmd, params=params, sender=f"{__name__}._updater"))
    ret = dreq.recv_pyobj()
    dreq.close()
    return ret


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    with_data: bool = False,
    **_: dict,
) -> Reply:
    """
    Get status of the tomato daemon.

    If ``with_data`` is specified, the state of the daemon will be retrieved.
    """
    logger.debug("checking status of tomato on port %d", port)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="status", with_data=with_data, sender=f"{__name__}.status"))
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    events = dict(poller.poll(timeout))
    if req in events:
        rep = req.recv_pyobj()
        return Reply(
            success=True,
            msg=f"tomato running on port {port}",
            data=rep.data,
        )
    else:
        req.setsockopt(zmq.LINGER, 0)
        req.close()
        return Reply(
            success=False,
            msg=f"tomato not running on port {port}",
        )


def start(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: Path,
    logdir: Path,
    verbosity: int,
    **_: dict,
) -> Reply:
    """
    Start the tomato daemon.
    """
    logger.debug("checking for availability of port %d", port)
    try:
        rep = context.socket(zmq.REP)
        rep.bind(f"tcp://127.0.0.1:{port}")
        stat = status(port=port, timeout=1000, context=context)
        rep.unbind(f"tcp://127.0.0.1:{port}")
        rep.setsockopt(zmq.LINGER, 0)
        rep.close()
        if stat.success:
            return Reply(
                success=False,
                msg=f"tomato-daemon already running on port {port}",
            )
    except zmq.error.ZMQError:
        return Reply(
            success=False,
            msg=f"required port {port} is already in use, choose a different one",
        )

    if not (appdir / "settings.toml").exists():
        return Reply(
            success=False,
            msg=f"settings file not found in {appdir}, run 'tomato init' to create one",
        )

    logger.debug("starting tomato on port %d", port)
    cmd = [
        "tomato-daemon",
        "-p",
        f"{port}",
        "-A",
        f"{appdir}",
        "-L",
        f"{logdir}",
        "-V",
        f"{verbosity}",
    ]
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)
    kwargs = dict(port=port, timeout=max(timeout, 5000), context=context)
    stat = status(**kwargs)
    if stat.success:
        return reload(**kwargs, appdir=appdir)
    else:
        return Reply(
            success=False,
            msg=f"failed to start tomato on port {port}: {stat.msg}",
            data=stat.data,
        )


def stop(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    **_: dict,
) -> Reply:
    """
    Stop a running tomato daemon.

    Will not stop the daemon if any jobs are running. Will create a state snapshot.
    """
    stat = status(port=port, timeout=timeout, context=context)
    if stat.success:
        req = context.socket(zmq.REQ)
        req.connect(f"tcp://127.0.0.1:{port}")
        req.send_pyobj(dict(cmd="stop"))
        rep = req.recv_pyobj()
        return rep
    else:
        return stat


def init(
    *,
    appdir: Path,
    datadir: Path,
    **_: dict,
) -> Reply:
    """
    Create a default settings.toml file.

    Will overwrite any existing settings.toml file.
    """
    defaults = textwrap.dedent(
        f"""\
        # Default settings for tomato-{VERSION}
        # Generated on {str(datetime.now(timezone.utc))}
        datadir = '{datadir.resolve()}'

        [jobs]
        storage = '{datadir.resolve() / 'Jobs'}'

        [devices]
        config = '{appdir.resolve() / 'devices.yml'}'

        [drivers]
        example_counter.testpar = 1234
        """
    )
    if not appdir.exists():
        logger.debug("creating directory '%s'", appdir.resolve())
        os.makedirs(appdir)
    with (appdir / "settings.toml").open("w", encoding="utf-8") as of:
        of.write(defaults)
    return Reply(
        success=True,
        msg=f"wrote default settings into {appdir / 'settings.toml'}",
    )


def reload(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: Path,
    **_: dict,
) -> Reply:
    """
    Reload settings.toml and devices.yaml files and reconfigure tomato daemon.
    """
    kwargs = dict(port=port, timeout=timeout, context=context)
    logger.debug("Loading settings.toml file from %s.", appdir)
    try:
        settings = toml.load(appdir / "settings.toml")
    except FileNotFoundError:
        return Reply(
            success=False,
            msg=f"settings file not found in {appdir}, run 'tomato init' to create one",
        )

    devicefile = load_device_file(Path(settings["devices"]["config"]))
    devs = {dev["name"]: Device(**dev) for dev in devicefile["devices"]}
    pips, cmps = get_pipelines(devs, devicefile["pipelines"])
    drvs = {dev.driver: Driver(name=dev.driver) for dev in devs.values()}
    logger.debug(f"{pips=}")
    logger.debug(f"{cmps=}")
    logger.debug(f"{devs=}")
    logger.debug(f"{drvs=}")
    for drv in drvs.keys():
        if drv in settings["drivers"]:
            drvs[drv].settings.update(settings["drivers"][drv])
    ret = status(**kwargs)
    if not ret.success:
        return ret
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(
            cmd="setup",
            settings=settings,
            pips=pips,
            devs=devs,
            drvs=drvs,
            cmps=cmps,
            sender=f"{__name__}.reload",
        )
    )
    ret = req.recv_pyobj()
    if ret.success:
        return Reply(
            success=True,
            msg=f"tomato on port {port} reloaded with settings from {appdir}",
            data=ret.data,
        )
    else:
        return Reply(
            success=False,
            msg=f"tomato on port {port} could not be reloaded: {ret.msg}",
            data=ret.data,
        )


def pipeline_load(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    pipeline: str,
    sampleid: str,
    **_: dict,
) -> Reply:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        tomato pipeline load <pipeline> <sampleid>

    """
    stat = status(port=port, timeout=timeout, context=context, with_data=True)
    if not stat.success:
        return stat

    if pipeline not in stat.data.pips:
        return Reply(success=False, msg=f"pipeline {pipeline!r} not found on tomato")
    pip = stat.data.pips[pipeline]

    if pip.sampleid is not None:
        return Reply(
            success=False, msg=f"pipeline {pipeline!r} is not empty, aborting", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(
            cmd="pipeline",
            params=dict(sampleid=sampleid, name=pipeline),
            sender=f"{__name__}.pipeline_load",
        ),
    )
    msg = req.recv_pyobj()
    return Reply(
        success=True, msg=f"loaded {sampleid!r} into {pipeline!r}", data=msg.data
    )


def pipeline_eject(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    pipeline: str,
    **_: dict,
) -> Reply:
    """
    Eject any sample present in a pipeline. Usage:

    .. code:: bash

        tomato pipeline eject <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context, with_data=True)
    if not stat.success:
        return stat

    if pipeline not in stat.data.pips:
        return Reply(
            success=False,
            msg=f"pipeline {pipeline!r} not found on tomato",
            data=stat.data.pips,
        )
    pip = stat.data.pips[pipeline]

    if pip.sampleid is None:
        return Reply(
            success=True, msg=f"pipeline {pipeline!r} was already empty", data=pip
        )

    if pip.jobid is not None:
        return Reply(
            success=False, msg="cannot eject from a running pipeline", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(
            cmd="pipeline",
            params=dict(sampleid=None, ready=False, name=pipeline),
            sender=f"{__name__}.pipeline_eject",
        )
    )
    rep = req.recv_pyobj()
    return Reply(
        success=True, msg=f"pipeline {pipeline!r} ejected succesffully", data=rep.data
    )


def pipeline_ready(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    pipeline: str,
    **_: dict,
) -> Reply:
    """
    Mark pipeline as ready. Usage:

    .. code:: bash

        pipeline ready <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context, with_data=True)
    if not stat.success:
        return stat

    if pipeline not in stat.data.pips:
        return Reply(
            success=False,
            msg=f"pipeline {pipeline!r} not found on tomato",
            data=stat.data.pips,
        )
    pip = stat.data.pips[pipeline]

    if pip.ready:
        return Reply(
            success=True, msg=f"pipeline {pipeline!r} was already ready", data=pip
        )

    if pip.jobid is not None:
        return Reply(
            success=False, msg="cannot mark a running pipeline as ready", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(
            cmd="pipeline",
            params=dict(ready=True, name=pipeline),
            sender=f"{__name__}.pipeline_ready",
        )
    )
    rep = req.recv_pyobj()
    return Reply(success=True, msg=f"pipeline {pipeline!r} set as ready", data=rep.data)
