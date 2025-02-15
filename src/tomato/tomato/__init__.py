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

from tomato.models import Reply, Pipeline, Device, Driver, Component, Daemon
from tomato.daemon.jobdb import jobdb_setup

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
        logger.debug("writing default devices to '%s'", yamlpath)
        with yamlpath.open("w") as outfile:
            yaml.dump(jsdata, outfile)
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
                    h = f"{dev.driver}:({dev.address},{ch})"
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
                if isinstance(comp["channel"], int):
                    logger.warning(
                        "Supplying 'channel' as an int is deprecated "
                        "and will stop working in tomato-2.0."
                    )
                    comp["channel"] = str(comp["channel"])
                if comp["channel"] not in dev.channels:
                    logger.error(
                        "channel %s not found on device '%s'",
                        comp["channel"],
                        comp["device"],
                    )
                    break
                h = f"{dev.driver}:({dev.address},{comp['channel']})"
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


def _status_helper(daemon: Daemon, yaml: bool, stgrp: str):
    if stgrp == "tomato":
        rep = Reply(
            success=True,
            msg=f"tomato running on port {daemon.port}",
            data=daemon,
        )
    elif stgrp == "pipelines":
        if yaml:
            rep = Reply(
                success=True,
                msg=f"tomato running on port {daemon.port}",
                data=daemon.pips,
            )
        else:
            ii = []
            for i in daemon.pips.values():
                line = f"name:{i.name}\tready:{i.ready}\tsampleid:{i.sampleid}\tjobid:{i.jobid}"
                ii.append(line)
            if len(ii) == 0:
                msg = f"tomato running on port {daemon.port} with no pipelines"
            else:
                msg = f"tomato running on port {daemon.port} with the following pipelines:\n\t "
                msg += "\n\t ".join(ii)
            rep = Reply(success=True, msg=msg)
    elif stgrp == "drivers":
        if yaml:
            rep = Reply(
                success=True,
                msg=f"tomato running on port {daemon.port}",
                data=daemon.drvs,
            )
        else:
            ii = []
            for i in daemon.drvs.values():
                line = f"name:{i.name}\tport:{i.port}\tpid:{i.pid}\tversion:{i.version}"
                ii.append(line)
            if len(ii) == 0:
                msg = f"tomato running on port {daemon.port} with no drivers"
            else:
                msg = f"tomato running on port {daemon.port} with the following drivers:\n\t "
                msg += "\n\t ".join(ii)
            rep = Reply(success=True, msg=msg)
    elif stgrp == "devices":
        if yaml:
            rep = Reply(
                success=True,
                msg=f"tomato running on port {daemon.port}",
                data=daemon.devs,
            )
        else:
            ii = []
            for i in daemon.devs.values():
                line = f"name:{i.name}\tdriver:{i.driver}\taddress:{i.address}\tchannels:{i.channels}"
                ii.append(line)
            if len(ii) == 0:
                msg = f"tomato running on port {daemon.port} with no devices"
            else:
                msg = f"tomato running on port {daemon.port} with the following devices:\n\t "
                msg += "\n\t ".join(ii)
            rep = Reply(success=True, msg=msg)
    elif stgrp == "components":
        if yaml:
            rep = Reply(
                success=True,
                msg=f"tomato running on port {daemon.port}",
                data=daemon.cmps,
            )
        else:
            ii = []
            for i in daemon.cmps.values():
                line = f"name:{i.name}\tdriver:{i.driver}\tdevice:{i.device}\trole:{i.role}"
                ii.append(line)
            if len(ii) == 0:
                msg = f"tomato running on port {daemon.port} with no components"
            else:
                msg = f"tomato running on port {daemon.port} with the following components:\n\t "
                msg += "\n\t ".join(ii)
            rep = Reply(success=True, msg=msg)
    return rep


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    stgrp: str = "tomato",
    yaml: bool = True,
    **_: dict,
) -> Reply:
    """
    Get status of the tomato daemon.

    Examples
    --------

    >>> # Status with a running daemon
    >>> tomato status
    Success: tomato running on port 1234

    >>> # Status without a running daemon
    >>> tomato status
    Failure: tomato not running on port 1234

    >>> # Status of a running daemon with data
    >>> tomato status -y
    data:
      appdir: /home/kraus/.config/tomato/1.0rc2.dev2
      cmps:
        [...]
      devs:
        [...]
      drvs:
        [...]
      jobs:
        [...]
      logdir: /home/kraus/.cache/tomato/1.0rc2.dev2/log
      nextjob: 1
      pips:
        [...]
      port: 1234
      settings:
        [...]
      status: running
      verbosity: 20
    msg: tomato running on port 1234
    success: true

    >>> # Status of all configured pipelines
    >>> tomato status pipelines
    Success: tomato running on port 1234 with the following pipelines:
         name:pip-counter       ready:False     sampleid:counter_1_0.1  jobid:None

    >>> # Status of all configured drivers
    >>> tomato status drivers
    Success: tomato running on port 1234 with the following drivers:
         name:example_counter   port:34747      pid:192318

    >>> # Status of all configured devices
    >>> tomato status devices
    Success: tomato running on port 1234 with the following devices:
         name:dev-counter       driver:example_counter  address:example-addr    channels:['1']

    >>> # Status of all configured components:
    >>> tomato status components
    Success: tomato running on port 1234 with the following components:
         name:example_counter:(example-addr,1)  driver:example_counter  device:dev-counter      role:counter

    """
    logger.debug("checking status of tomato on port %d", port)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_pyobj(dict(cmd="status", sender=f"{__name__}.status"))
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    events = dict(poller.poll(timeout))
    if req in events:
        rep = req.recv_pyobj()
        return _status_helper(daemon=rep.data, yaml=yaml, stgrp=stgrp)
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
    verbosity: int,
    **_: dict,
) -> Reply:
    """
    Start the tomato daemon.

    Examples
    --------

    >>> # Start tomato
    >>> tomato start
    Success: tomato on port 1234 reloaded with settings from /home/kraus/.config/tomato/1.0rc2.dev2

    >>> # Start tomato with a custom port
    >>> tomato start -p 1235
    Success: tomato on port 1235 reloaded with settings from /home/kraus/.config/tomato/1.0rc2.dev2

    >>> # Start tomato with another tomato running
    >>> tomato start
    Failure: required port 1234 is already in use, choose a different one

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

    if not (Path(appdir) / "settings.toml").exists():
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

    Examples
    --------

    >>> # Stop tomato daemon without running jobs
    >>> tomato stop
    Success: tomato on port 1234 closed successfully

    >>> # Attempt to stop tomato daemon with running jobs
    >>> tomato stop
    Failure: jobs are running

    >>> # Attempt to stop tomato daemon which is not running
    >>> tomato stop -p 1235
    Failure: tomato not running on port 1235

    """
    stat = status(port=port, timeout=timeout, context=context)
    if stat.success:
        req = context.socket(zmq.REQ)
        req.connect(f"tcp://127.0.0.1:{port}")
        req.send_pyobj(dict(cmd="stop"))
        rep = req.recv_pyobj()
        if rep.success:
            return Reply(success=True, msg=f"tomato on port {port} closed successfully")
        else:
            return rep
    else:
        return stat


def init(
    *,
    appdir: str,
    datadir: str,
    logdir: str,
    **_: dict,
) -> Reply:
    """
    Create a default settings.toml file.

    Will overwrite any existing settings.toml file.

    Examples
    --------

    >>> tomato init
    Success: wrote default settings into /home/kraus/.config/tomato/1.0rc2.dev2/settings.toml

    """
    appdir = Path(appdir).resolve()
    datadir = Path(datadir).resolve()
    logdir = Path(logdir).resolve()
    storage = datadir.resolve() / "Jobs"
    dbpath = storage / "dbpath.sqlite"
    defaults = textwrap.dedent(
        f"""\
        # Default settings for tomato-{VERSION}
        # Generated on {str(datetime.now(timezone.utc))}
        datadir = '{datadir}'
        logdir = '{logdir}'

        [jobs]
        storage = '{storage}'
        dbpath = '{dbpath}'

        [devices]
        config = '{appdir / "devices.yml"}'

        [drivers]
        example_counter.testpar = 1234
        """
    )
    if not appdir.exists():
        logger.debug("creating directory '%s'", appdir)
        os.makedirs(appdir)
    with (appdir / "settings.toml").open("w", encoding="utf-8") as of:
        of.write(defaults)
    if not logdir.exists():
        logger.debug("creating directory '%s'", logdir)
        os.makedirs(logdir)
    if not storage.exists():
        logger.debug("creating directory '%s'", storage)
        os.makedirs(storage)
    if not dbpath.exists():
        jobdb_setup(dbpath)
    return Reply(
        success=True,
        msg=f"wrote default settings into {appdir / 'settings.toml'}",
    )


def reload(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    **_: dict,
) -> Reply:
    """
    Reload settings.toml and devices.yaml files and reconfigure tomato daemon.

    Examples
    --------

    >>> # Reload with compatible changes
    >>> tomato reload
    Success: tomato on port 1234 reloaded with settings from /home/kraus/.config/tomato/1.0rc2.dev2

    """
    kwargs = dict(port=port, timeout=timeout, context=context)
    logger.debug("Loading settings.toml file from %s.", appdir)
    try:
        settings = toml.load(Path(appdir) / "settings.toml")
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
    stat = status(port=port, timeout=timeout, context=context)
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
    stat = status(port=port, timeout=timeout, context=context)
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
    stat = status(port=port, timeout=timeout, context=context)
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
