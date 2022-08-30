"""
Main module - executables for tomato.

"""
import argparse
import logging
import psutil
import os
from importlib import metadata

from . import daemon
from . import dbhandler
from . import setlib
from . import ketchup

log = logging.getLogger(__name__)


def _logging_setup(args):
    loglevel = min(max(30 + 10 * (args.quiet - args.verbose), 10), 50)
    logging.basicConfig(level=loglevel)
    log.debug(f"loglevel set to '{logging._levelToName[loglevel]}'")


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


def sync_pipelines_to_state(
    pipelines: list,
    dbpath: str,
    type: str = "sqlite3",
) -> None:
    pstate = dbhandler.pipeline_get_all(dbpath, type)
    for pip in pipelines:
        log.debug(f"checking presence of pipeline '{pip['name']}' in 'state'")
        if pip["name"] not in pstate:
            dbhandler.pipeline_insert(dbpath, pip["name"], type)
    pnames = [p["name"] for p in pipelines]
    for pname in pstate:
        if pname not in pnames:
            dbhandler.pipeline_remove(dbpath, pname, type)
    pstate = dbhandler.pipeline_get_all(dbpath, type)


def run_tomato():
    parser, _ = _default_parsers()
    args = parser.parse_args()
    _logging_setup(args)

    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()

    procs = psutil.process_iter(['pid', 'name'])
    toms = [p.pid for p in procs if p.name() in {"tomato", "tomato.exe"}]
    toms.pop(toms.index(pid))
    if len(toms) > 0 and not args.test:
        logging.critical("cannot run more than one instance of 'tomato'")
        logging.info(f"'tomato' is currently running as pid {toms}")
        return

    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    pipelines = setlib.get_pipelines(settings["devices"]["path"])
    log.debug(f"setting up 'queue' table in '{settings['queue']['path']}'")
    dbhandler.queue_setup(settings["queue"]["path"], type=settings["queue"]["type"])
    log.debug(f"setting up 'state' table in '{settings['queue']['path']}'")
    dbhandler.state_setup(settings["state"]["path"], type=settings["state"]["type"])
    sync_pipelines_to_state(
        pipelines, settings["state"]["path"], type=settings["state"]["type"]
    )

    daemon.main_loop(settings, pipelines, test=args.test)


def run_ketchup():
    parser, verbose = _default_parsers()
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
        "jobid",
        nargs="*",
        help=(
            "The jobid of the requested job, "
            "or 'queue' for the status of the queue,"
            "or 'state' for the status of pipelines."
        ),
        default=["state"],
    )
    status.set_defaults(func=ketchup.status)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument(
        "jobid", help="The jobid of the job to be cancelled.", default=None
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

    args, extras = parser.parse_known_args()
    args, extras = verbose.parse_known_args(extras, args)
    _logging_setup(args)

    if "func" in args:
        args.func(args)
