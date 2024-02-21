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
import time

import logging
import psutil
import zmq
import yaml
import toml

from tomato.models import Reply, Pipeline, Device, Driver

logger = logging.getLogger(__name__)

DEFAULT_TOMATO_PORT = 1234
VERSION = metadata.version("tomato")


def set_loglevel(delta: int):
    loglevel = min(max(30 - (10 * delta), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def load_device_file(yamlpath: Path) -> dict:
    logger.debug(f"loading device file from '{yamlpath}'")
    try:
        with yamlpath.open("r") as infile:
            jsdata = yaml.safe_load(infile)
    except FileNotFoundError:
        logger.error("device file not found. Running with default devices.")
        devpath = Path(__file__).parent / ".." / "data" / "default_devices.json"
        with devpath.open() as inp:
            jsdata = json.load(inp)
    return jsdata


def get_pipelines(devs: dict[str, Device], pipelines: list) -> dict[str, Pipeline]:
    pips = {}
    for pip in pipelines:
        if "*" in pip["name"]:
            data = {"name": pip["name"], "devs": {}}
            if len(pip["devices"]) > 1:
                logger.error("more than one component in a wildcard pipeline")
                continue
            for comp in pip["devices"]:
                if comp["name"] not in devs:
                    logger.error(f"component {comp['name']} not found among devices")
                    break
                dev = devs[comp["name"]]
                for ch in dev.channels:
                    name = pip["name"].replace("*", f"{ch}")
                    d = {dev.name: dict(role=comp["tag"], channel=ch)}
                    p = dict(name=name, devs=d)
                    pips[name] = Pipeline(**p)
        else:
            data = {"name": pip["name"], "devs": {}}
            for comp in pip["devices"]:
                if comp["name"] not in devs:
                    logger.error(f"component {comp['name']} not found among devices")
                    break
                dev = devs[comp["name"]]
                if comp["channel"] not in dev.channels:
                    logger.error(f"channel {comp['channel']} not found among channels")
                    break
                data["devs"][dev.name] = dict(role=comp["tag"], channel=comp["channel"])
            pips[pip["name"]] = Pipeline(**data)
    return pips


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    with_data: bool = False,
    **_: dict,
) -> Reply:
    logger.debug(f"checking status of tomato on port {port}")
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
    logger.debug(f"checking for availability of port {port}.")
    try:
        rep = context.socket(zmq.REP)
        rep.bind(f"tcp://127.0.0.1:{port}")
        rep.unbind(f"tcp://127.0.0.1:{port}")
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

    logger.debug(f"starting tomato on port {port}")
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
        time.sleep(2)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)
    kwargs = dict(port=port, timeout=timeout, context=context)
    stat = status(**kwargs)
    if stat.success:
        return reload(**kwargs, appdir=appdir)
    else:
        return Reply(
            success=False,
            msg=f"failed to start tomato on port {port}: {stat.msg}",
            data=stat.data,
        )


def stop(*, port: int, timeout: int, context: zmq.Context, **_: dict) -> Reply:
    stat = status(port=port, timeout=timeout, context=context)
    if stat.success:
        req = context.socket(zmq.REQ)
        req.connect(f"tcp://127.0.0.1:{port}")
        req.send_pyobj(dict(cmd="stop"))
        rep = req.recv_pyobj()
        if rep.msg == "stop":
            return Reply(
                success=True,
                msg=f"tomato on port {port} was instructed to stop",
            )
        else:
            return Reply(
                success=False,
                msg=f"unknown error: {rep.msg}",
                data=rep.data,
            )
    else:
        return stat


def init(
    *,
    appdir: Path,
    datadir: Path,
    **_: dict,
) -> Reply:
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
        """
    )
    if not appdir.exists():
        logger.debug(f"creating directory '{appdir.resolve()}'")
        os.makedirs(appdir)
    with (appdir / "settings.toml").open("w", encoding="utf-8") as of:
        of.write(defaults)
    return Reply(
        success=True,
        msg=f"wrote default settings into {appdir / 'settings.toml'}",
    )


def reload(
    *, port: int, timeout: int, context: zmq.Context, appdir: Path, **_: dict
) -> Reply:
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
    pips = get_pipelines(devs, devicefile["pipelines"])
    drvs = [Driver(name=dev.driver) for dev in devs.values()]
    for drv in drvs:
        if drv.name in settings["drivers"]:
            drv.settings.update(settings["drivers"][drv.name])

    stat = status(port=port, timeout=timeout, context=context, with_data=True)
    if not stat.success:
        return stat
    daemon = stat.data

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    if daemon.status == "bootstrap":
        for drv in drvs:
            req.send_pyobj(
                dict(
                    cmd="driver",
                    name=drv.name,
                    params=dict(settings=drv.settings),
                    sender=f"{__name__}.reload",
                )
            )
            rep = req.recv_pyobj()
    elif daemon.status == "running":
        pass
        #assert False, "not yet implemented"
        #for drv in drvs:
        #    if drv.settings != daemon.drvs[drv.name].settings:
        #        if daemon.drvs[drv.name].port is None:
        #            logger.error(f"driver {drv.name!r} is not online, cannot reload")
        #            continue
        #        dreq = context.socket(zmq.REQ)
        #        dreq.connect(f"tcp://127.0.0.1:{daemon.drvs[drv.name].port}")

    req.send_pyobj(
        dict(
            cmd="setup",
            settings=settings,
            pips=pips,
            devs=devs,
            sender="tomato.tomato.reload",
        )
    )
    rep = req.recv_pyobj()
    if rep.msg == "running":
        return Reply(
            success=True,
            msg=f"tomato configured on port {port} with settings from {appdir}",
            data=rep.data,
        )
    else:
        return Reply(
            success=False,
            msg=f"tomato configuration on port {port} failed: {rep.msg}",
            data=rep.data,
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

        tomato pipeline load <samplename> <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context, with_data=True)
    if not stat.success:
        return stat

    if pipeline not in stat.data.pips:
        return Reply(success=False, msg=f"pipeline {pipeline!r} not found on tomato")
    logger.critical(f"{stat.data.pips[pipeline]=}")
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
            pipeline=pipeline,
            params=dict(sampleid=sampleid),
            sender="tomato.tomato.pipeline_load",
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
            pipeline=pipeline,
            params=dict(sampleid=None, ready=False),
            sender="tomato.tomato.pipeline_eject",
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
            pipeline=pipeline,
            params=dict(ready=True),
            sender="tomato.tomato.pipeline_ready",
        )
    )
    rep = req.recv_pyobj()
    return Reply(success=True, msg=f"pipeline {pipeline!r} set as ready", data=rep.data)
