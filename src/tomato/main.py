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

logger = logging.getLogger(__name__)

DEFAULT_TOMATO_PORT = 1234
VERSION = metadata.version("tomato")


def set_loglevel(delta: int):
    loglevel = min(max(30 - (10 * delta), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def sync_pipelines_to_state(
    pipelines: list,
    dbpath: str,
    type: str = "sqlite3",
) -> None:
    pstate = dbhandler.pipeline_get_all(dbpath, type)
    for pip in pipelines:
        logger.debug(f"checking presence of pipeline '{pip['name']}' in 'state'")
        if pip["name"] not in pstate:
            dbhandler.pipeline_insert(dbpath, pip["name"], type)
    pnames = [p["name"] for p in pipelines]
    for pname in pstate:
        if pname not in pnames:
            dbhandler.pipeline_remove(dbpath, pname, type)
    pstate = dbhandler.pipeline_get_all(dbpath, type)


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
    req.send_json(dict(cmd="status"))

    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    events = dict(poller.poll(timeout))
    if req in events:
        data = req.recv_json()
        return dict(
            success=True,
            msg=f"tomato running on port {port}",
            data=data,
        )
    else:
        req.setsockopt(zmq.LINGER, 0)
        req.close()
        return dict(
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
        return dict(
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

    status = tomato_status(port=port, timeout=1000, context=context)
    if status["success"]:
        return tomato_reload(
            port=port, timeout=timeout, context=context, appdir=appdir, **kwargs
        )
    else:
        return dict(
            success=False,
            msg=f"failed to start tomato on port {port}",
            data=status,
        )


def tomato_stop(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    **_: dict,
):
    status = tomato_status(port=port, timeout=timeout, context=context)
    if status["success"]:
        req = context.socket(zmq.REQ)
        req.connect(f"tcp://127.0.0.1:{port}")
        req.send_json(dict(cmd="stop"))
        msg = req.recv_json()
        if msg["status"] == "stop":
            return dict(
                success=True,
                msg=f"tomato on port {port} was instructed to stop",
                data=msg,
            )
        else:
            return dict(
                success=False,
                msg="unknown error",
                data=msg,
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
    return dict(
        success=True,
        msg=f"wrote default settings into {Path(appdir) / 'settings.toml'}",
    )


def tomato_reload(
    *,
    port: int,
    context: zmq.Context,
    appdir: str,
    **_: dict,
) -> dict:
    logging.debug("Loading settings.toml file from %s.", appdir)
    try:
        settings = toml.load(Path(appdir) / "settings.toml")
    except FileNotFoundError:
        return dict(
            success=False,
            msg=f"settings.toml file not found in {appdir}, run 'tomato init' to create one",
        )

    pipelines = setlib.get_pipelines(settings["devices"]["path"])

    logger.debug(f"setting up 'queue' table in '{settings['queue']['path']}'")
    dbhandler.queue_setup(settings["queue"]["path"], type=settings["queue"]["type"])
    logger.debug(f"setting up 'state' table in '{settings['queue']['path']}'")
    dbhandler.state_setup(settings["state"]["path"], type=settings["state"]["type"])
    sync_pipelines_to_state(
        pipelines, settings["state"]["path"], type=settings["state"]["type"]
    )

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    req.send_json(dict(cmd="setup", settings=settings, pipelines=pipelines))
    msg = req.recv_json()
    if msg["status"] == "running":
        return dict(
            success=True,
            msg=f"tomato configured on port {port} with settings from {appdir}",
            data=msg,
        )
    else:
        return dict(
            success=False,
            msg=f"tomato configuration on port {port} failed",
            data=msg,
        )


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

    for p in [start, stop, init, status, reload]:
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
        print(yaml.dump(ret))


def _logging_setup(args):
    loglevel = min(max(30 + 10 * (args.quiet - args.verbose), 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug(f"loglevel set to '{logging._levelToName[loglevel]}'")


def _default_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        default=False,
        help="Launch tomato in test mode.",
    )

    verbose = argparse.ArgumentParser(add_help=False)
    for p in [parser, verbose]:
        p.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Increase verbosity by one level.",
        )
        p.add_argument(
            "-q",
            "--quiet",
            action="count",
            default=0,
            help="Decrease verbosity by one level.",
        )
    return parser, verbose


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

    load = subparsers.add_parser("load")
    load.add_argument("sample", help="Name of the sample to be loaded.", default=None)
    load.add_argument(
        "pipeline", help="Name of the pipeline to load the sample to.", default=None
    )
    load.set_defaults(func=ketchup.load)

    eject = subparsers.add_parser("eject")
    eject.add_argument(
        "pipeline", help="Name of the pipeline to eject any sample from.", default=None
    )
    eject.set_defaults(func=ketchup.eject)

    ready = subparsers.add_parser("ready")
    ready.add_argument(
        "pipeline", help="Name of the pipeline to mark as ready.", default=None
    )
    ready.set_defaults(func=ketchup.ready)

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

    for p in [submit, status, cancel, load, eject, ready, snapshot, search]:
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
        ret = args.func(**vars(args), verbosity=verbosity)
        print(yaml.dump(ret))
