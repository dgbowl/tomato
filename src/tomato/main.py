"""
Main module - executables for tomato.

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

from . import dbhandler
from . import setlib
from . import ketchup

from tomato.models import Reply, Pipeline

logger = logging.getLogger(__name__)

DEFAULT_TOMATO_PORT = 1234
VERSION = metadata.version("tomato")


def set_loglevel(delta: int):
    loglevel = min(max(30 - (10 * delta), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def tomato_status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    **_: dict,
) -> dict:
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


def tomato_start(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    **kwargs: dict,
) -> dict:
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

    status = tomato_status(port=port, timeout=timeout, context=context)
    if status.success:
        return tomato_reload(
            port=port, timeout=timeout, context=context, appdir=appdir, **kwargs
        )
    else:
        return Reply(
            success=False,
            msg=f"failed to start tomato on port {port}: {status.msg}",
            data=status.data,
        )


def tomato_stop(*, port: int, timeout: int, context: zmq.Context, **_: dict):
    status = tomato_status(port=port, timeout=timeout, context=context)
    if status.success:
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
        return status


def tomato_init(
    *,
    appdir: str,
    datadir: str,
    **_: dict,
) -> dict:
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


def tomato_reload(
    *, port: int, timeout: int, context: zmq.Context, appdir: str, **_: dict
) -> dict:
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

    status = tomato_status(port=port, timeout=timeout, context=context)
    if not status.success:
        return status
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


def tomato_pipeline_load(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    pipeline: str,
    sampleid: str,
    **_: dict,
) -> dict:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] load <samplename> <pipeline>

    Assigns the sample with the provided ``samplename`` into the ``pipeline``.
    Checks whether the pipeline exists and whether it is empty before loading
    sample.

    """
    status = tomato_status(port=port, timeout=timeout, context=context)
    if not status.success:
        return status

    pipnames = [pip.name for pip in status.data]
    if pipeline not in pipnames:
        return Reply(success=False, msg=f"pipeline {pipeline} not found on tomato")
    pip = status.data[pipnames.index(pipeline)]

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


def tomato_pipeline_eject(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    pipeline: str,
    **_: dict,
) -> dict:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] load <samplename> <pipeline>

    Assigns the sample with the provided ``samplename`` into the ``pipeline``.
    Checks whether the pipeline exists and whether it is empty before loading
    sample.

    """
    status = tomato_status(port=port, timeout=timeout, context=context)
    if not status.success:
        return status

    pipnames = [pip.name for pip in status.data]
    if pipeline not in pipnames:
        return Reply(
            success=False,
            msg=f"pipeline {pipeline} not found on tomato",
            data=pipnames,
        )
    pip = status.data[pipnames.index(pipeline)]

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


def tomato_pipeline_ready(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    appdir: str,
    pipeline: str,
    **_: dict,
) -> dict:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] load <samplename> <pipeline>

    Assigns the sample with the provided ``samplename`` into the ``pipeline``.
    Checks whether the pipeline exists and whether it is empty before loading
    sample.

    """
    status = tomato_status(port=port, timeout=timeout, context=context)
    if not status.success:
        return status

    pipnames = [pip.name for pip in status.data]
    if pipeline not in pipnames:
        return Reply(
            success=False, msg=f"pipeline {pipeline} not found on tomato", data=pipnames
        )
    pip = status.data[pipnames.index(pipeline)]

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


def run_tomato():
    dirs = appdirs.AppDirs("tomato", "dgbowl", version=VERSION)
    config_dir = dirs.user_config_dir
    data_dir = dirs.user_data_dir

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )

    verbose = argparse.ArgumentParser(add_help=False)

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    status = subparsers.add_parser("status")
    status.set_defaults(func=tomato_status)

    start = subparsers.add_parser("start")
    start.set_defaults(func=tomato_start)

    stop = subparsers.add_parser("stop")
    stop.set_defaults(func=tomato_stop)

    init = subparsers.add_parser("init")
    init.set_defaults(func=tomato_init)

    reload = subparsers.add_parser("reload")
    reload.set_defaults(func=tomato_reload)

    pipeline = subparsers.add_parser("pipeline")
    pipparsers = pipeline.add_subparsers(dest="subsubcommand", required=True)

    pip_load = pipparsers.add_parser("load")
    pip_load.set_defaults(func=tomato_pipeline_load)
    pip_load.add_argument(
        "pipeline",
    )
    pip_load.add_argument(
        "sampleid",
    )

    pip_eject = pipparsers.add_parser("eject")
    pip_eject.set_defaults(func=tomato_pipeline_eject)
    pip_eject.add_argument(
        "pipeline",
    )

    pip_ready = pipparsers.add_parser("ready")
    pip_ready.set_defaults(func=tomato_pipeline_ready)
    pip_ready.add_argument(
        "pipeline",
    )

    for p in [parser, verbose]:
        p.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity by one level.",
        )
        p.add_argument(
            "--quiet",
            "-q",
            action="count",
            default=0,
            help="Decrease verbosity by one level.",
        )

    for p in [start, stop, init, status, reload, pip_load, pip_eject, pip_ready]:
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the tomato command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--appdir",
            help="Settings directory for tomato",
            default=config_dir,
        )
        p.add_argument(
            "--datadir",
            help="Data directory for tomato",
            default=data_dir,
        )

    # parse subparser args
    args, extras = parser.parse_known_args()
    # parse extras for verbose tags
    args, extras = verbose.parse_known_args(extras, args)

    set_loglevel(args.verbose - args.quiet)

    context = zmq.Context()
    if "func" in args:
        ret = args.func(**vars(args), context=context)
        print(yaml.dump(ret.dict()))


def run_ketchup():
    dirs = appdirs.AppDirs("tomato", "dgbowl", version=VERSION)
    config_dir = dirs.user_config_dir
    data_dir = dirs.user_data_dir

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )

    verbose = argparse.ArgumentParser(add_help=False)

    for p in [parser, verbose]:
        p.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity by one level.",
        )
        p.add_argument(
            "--quiet",
            "-q",
            action="count",
            default=0,
            help="Decrease verbosity by one level.",
        )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    submit = subparsers.add_parser("submit")
    submit.add_argument(
        "payload",
        help="File containing the payload to be submitted to tomato.",
        default=None,
    )
    submit.add_argument(
        "-j",
        "--jobname",
        help="Set the job name of the submitted job to?",
        default=None,
    )
    submit.set_defaults(func=ketchup.submit)

    status = subparsers.add_parser("status")
    status.add_argument(
        "jobids",
        nargs="*",
        help=(
            "The jobid(s) of the requested job(s), "
            "defaults to the status of the whole queue."
        ),
        type=int,
        default=None,
    )
    status.set_defaults(func=ketchup.status)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument(
        "jobid",
        help="The jobid of the job to be cancelled.",
        type=int,
        default=None,
    )
    cancel.set_defaults(func=ketchup.cancel)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument(
        "jobid", help="The jobid of the job to be snapshotted.", default=None
    )
    snapshot.set_defaults(func=ketchup.snapshot)

    search = subparsers.add_parser("search")
    search.add_argument(
        "jobname",
        help="The jobname of the searched job.",
        default=None,
    )
    search.add_argument(
        "-c",
        "--complete",
        action="store_true",
        default=False,
        help="Search also in completed jobs.",
    )
    search.set_defaults(func=ketchup.search)

    for p in [submit, status, cancel, snapshot, search]:
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the ketchup command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--appdir",
            help="Settings directory for tomato",
            default=config_dir,
        )
        p.add_argument(
            "--datadir",
            help="Data directory for tomato",
            default=data_dir,
        )

    args, extras = parser.parse_known_args()
    args, extras = verbose.parse_known_args(extras, args)

    verbosity = args.verbose - args.quiet
    set_loglevel(verbosity)

    if "func" in args:
        context = zmq.Context()
        status = tomato_status(**vars(args), context=context)
        if not status.success:
            print(yaml.dump(status.dict()))
        else:
            ret = args.func(
                **vars(args), verbosity=verbosity, context=context, status=status
            )
            print(yaml.dump(ret.dict()))
