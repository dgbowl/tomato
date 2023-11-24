"""
**tomato**: command line interface to the tomato daemon
-------------------------------------------------------
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
from pathlib import Path
from datetime import datetime, timezone
from importlib import metadata

import argparse
import logging
import psutil
import zmq
import appdirs
import yaml
import toml

from tomato import dbhandler, setlib, ketchup
from tomato.models import Reply, Pipeline

logger = logging.getLogger(__name__)

DEFAULT_TOMATO_PORT = 1234
VERSION = metadata.version("tomato")


def set_loglevel(delta: int):
    loglevel = min(max(30 - (10 * delta), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    **_: dict,
) -> Reply:
    logger.debug(f"checking status of tomato on port {port}")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="status"))

    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    events = dict(poller.poll(timeout))
    if req in events:
        rep = req.recv_pyobj()
        trimmed = []
        for pip in rep.data:
            shortpip = Pipeline(
                name=pip.name,
                ready=pip.ready,
                jobid=pip.jobid,
                sampleid=pip.sampleid,
            )
            trimmed.append(shortpip)
        rep.data = trimmed
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
    appdir: str,
    **kwargs: dict,
) -> Reply:
    logging.debug(f"checking for availability of port {port}.")
    try:
        rep = context.socket(zmq.REP)
        rep.bind(f"tcp://127.0.0.1:{port}")
        rep.unbind(f"tcp://127.0.0.1:{port}")
    except zmq.error.ZMQError:
        return Reply(
            success=False,
            msg=f"required port {port} is already in use, choose a different one",
        )

    logger.debug(f"starting tomato on port {port}")
    cmd = ["tomato-daemon", "--port", f"{port}"]
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)

    stat = status(port=port, timeout=timeout, context=context)
    if stat.success:
        return reload(
            port=port, timeout=timeout, context=context, appdir=appdir, **kwargs
        )
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
    appdir: str,
    datadir: str,
    **_: dict,
) -> Reply:
    ddir = Path(datadir)
    adir = Path(appdir)

    defaults = textwrap.dedent(
        f"""\
        # Default settings for tomato-{VERSION}
        # Generated on {str(datetime.now(timezone.utc))}
        [state]
        type = 'sqlite3'
        path = '{ddir / 'database.db'}'

        [queue]
        type = 'sqlite3'
        path = '{ddir / 'database.db'}'
        storage = '{ddir / 'Jobs'}'

        [devices]
        path = '{adir / 'devices.yml'}'

        [drivers]
        """
    )
    if not adir.exists():
        logging.debug("creating directory '%s'", adir)
        os.makedirs(adir)
    with open(adir / "settings.toml", "w", encoding="utf-8") as of:
        of.write(defaults)
    return Reply(
        success=True,
        msg=f"wrote default settings into {Path(appdir) / 'settings.toml'}",
    )


def reload(
    *, port: int, timeout: int, context: zmq.Context, appdir: str, **_: dict
) -> Reply:
    logging.debug("Loading settings.toml file from %s.", appdir)
    try:
        settings = toml.load(Path(appdir) / "settings.toml")
    except FileNotFoundError:
        return Reply(
            success=False,
            msg=f"settings file not found in {appdir}, run 'tomato init' to create one",
        )

    pipelines = setlib.get_pipelines(settings["devices"]["path"])

    logger.debug(f"setting up 'queue' table in '{settings['queue']['path']}'")
    dbhandler.queue_setup(settings["queue"]["path"], type=settings["queue"]["type"])

    stat = status(port=port, timeout=timeout, context=context)
    if not stat.success:
        return stat
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="setup", settings=settings, pipelines=pipelines))
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
    appdir: str,
    pipeline: str,
    sampleid: str,
    **_: dict,
) -> Reply:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        tomato pipeline load <samplename> <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context)
    if not stat.success:
        return stat

    pipnames = [pip.name for pip in stat.data]
    if pipeline not in pipnames:
        return Reply(success=False, msg=f"pipeline {pipeline} not found on tomato")
    pip = stat.data[pipnames.index(pipeline)]

    if pip.sampleid is not None:
        return Reply(
            success=False, msg=f"pipeline {pipeline} is not empty, aborting", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(cmd="pipeline", pipeline=pipeline, params=dict(sampleid=sampleid))
    )
    msg = req.recv_pyobj()
    return Reply(success=True, msg=f"loaded {sampleid} into {pipeline}", data=msg.data)


def pipeline_eject(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    pipeline: str,
    **_: dict,
) -> Reply:
    """
    Eject any sample present in a pipeline. Usage:

    .. code:: bash

        tomato pipeline eject <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context)
    if not stat.success:
        return stat

    pipnames = [pip.name for pip in stat.data]
    if pipeline not in pipnames:
        return Reply(
            success=False,
            msg=f"pipeline {pipeline} not found on tomato",
            data=pipnames,
        )
    pip = stat.data[pipnames.index(pipeline)]

    if pip.sampleid is None:
        return Reply(
            success=True, msg=f"pipeline {pipeline} was already empty", data=pip
        )

    if pip.jobid is not None:
        return Reply(
            success=False, msg="cannot eject from a running pipeline", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(
        dict(cmd="pipeline", pipeline=pipeline, params=dict(sampleid=None, ready=False))
    )
    rep = req.recv_pyobj()
    return Reply(
        success=True, msg=f"pipeline {pipeline} ejected succesffully", data=rep.data
    )


def pipeline_ready(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    pipeline: str,
    **_: dict,
) -> Reply:
    """
    Mark pipeline as ready. Usage:

    .. code:: bash

        pipeline ready <pipeline>

    """
    stat = status(port=port, timeout=timeout, context=context)
    if not stat.success:
        return stat

    pipnames = [pip.name for pip in stat.data]
    if pipeline not in pipnames:
        return Reply(
            success=False, msg=f"pipeline {pipeline} not found on tomato", data=pipnames
        )
    pip = stat.data[pipnames.index(pipeline)]

    if pip.ready:
        return Reply(
            success=True, msg=f"pipeline {pipeline} was already ready", data=pip
        )

    if pip.jobid is not None:
        return Reply(
            success=False, msg="cannot mark a running pipeline as ready", data=pip
        )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="pipeline", pipeline=pipeline, params=dict(ready=True)))
    rep = req.recv_pyobj()
    return Reply(success=True, msg=f"pipeline {pipeline} set as ready", data=rep.data)