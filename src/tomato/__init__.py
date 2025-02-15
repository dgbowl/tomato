import sys
from pathlib import Path

from importlib import metadata
import argparse
import logging
import zmq
import appdirs
import yaml

from tomato import tomato, ketchup, passata

sys.path += sys.modules["tomato"].__path__

__version__ = metadata.version("tomato")
VERSION = __version__
DEFAULT_TOMATO_PORT = 1234
logger = logging.getLogger(__name__)


def set_loglevel(loglevel: int):
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])


def parse_args(parser, verbose, is_tomato=False):
    args, extras = parser.parse_known_args()
    args, extras = verbose.parse_known_args(extras, args)

    verbosity = min(max((2 + args.quiet - args.verbose) * 10, 10), 50)
    set_loglevel(verbosity)

    context = zmq.Context()
    if not is_tomato:
        status = tomato.status(**vars(args), context=context)
        if not status.success:
            if args.yaml:
                print(yaml.dump(status.dict()))
            else:
                print(f"Failure: {status.msg}")

    if "func" in args:
        ret = args.func(**vars(args), verbosity=verbosity, context=context)
        if args.yaml:
            print(yaml.dump(ret.dict()))
        else:
            print(f"{'Success' if ret.success else 'Failure'}: {ret.msg}")


def run_tomato():
    dirs = appdirs.AppDirs("tomato", "dgbowl", version=VERSION)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )

    verbose = argparse.ArgumentParser(add_help=False)

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    status = subparsers.add_parser("status")
    status.add_argument(
        "stgrp",
        choices=["tomato", "pipelines", "drivers", "devices", "components"],
        default="tomato",
        nargs="?",
        help="Check status of 'tomato', or its 'pipelines', 'drivers', 'devices', or 'components'.",
    )
    status.set_defaults(func=tomato.status)

    start = subparsers.add_parser("start")
    start.set_defaults(func=tomato.start)

    stop = subparsers.add_parser("stop")
    stop.set_defaults(func=tomato.stop)

    init = subparsers.add_parser("init")
    init.set_defaults(func=tomato.init)

    reload = subparsers.add_parser("reload")
    reload.set_defaults(func=tomato.reload)

    pipeline = subparsers.add_parser("pipeline")
    pipparsers = pipeline.add_subparsers(dest="subsubcommand", required=True)

    pip_load = pipparsers.add_parser("load")
    pip_load.set_defaults(func=tomato.pipeline_load)
    pip_load.add_argument("pipeline")
    pip_load.add_argument("sampleid")

    pip_eject = pipparsers.add_parser("eject")
    pip_eject.set_defaults(func=tomato.pipeline_eject)
    pip_eject.add_argument("pipeline")

    pip_ready = pipparsers.add_parser("ready")
    pip_ready.set_defaults(func=tomato.pipeline_ready)
    pip_ready.add_argument("pipeline")

    for p in [parser, verbose]:
        p.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Increase verbosity of tomato daemon by one level.",
        )
        p.add_argument(
            "--quiet",
            "-q",
            action="count",
            default=0,
            help="Decrease verbosity of tomato daemon by one level.",
        )

    for p in [start, stop, init, status, reload, pip_load, pip_eject, pip_ready]:
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
            type=int,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the tomato command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--yaml",
            "-y",
            help="Return output as a yaml.",
            action="store_true",
            default=False,
        )

    for p in [start, init, reload]:
        p.add_argument(
            "--appdir",
            "-A",
            type=Path,
            help="Settings directory for tomato",
            default=Path(dirs.user_config_dir),
        )
    for p in [init]:
        p.add_argument(
            "--datadir",
            "-D",
            type=Path,
            help="Data directory for tomato",
            default=Path(dirs.user_data_dir),
        )
        p.add_argument(
            "--logdir",
            "-L",
            type=Path,
            help="Log directory for tomato",
            default=Path(dirs.user_log_dir),
        )

    parse_args(parser, verbose, is_tomato=True)


def run_ketchup():
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
            "The job.id(s) of the job(s) to be checked. "
            "Defaults to the status of the whole queue."
        ),
        type=int,
        default=None,
    )
    status.set_defaults(func=ketchup.status)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument(
        "jobids",
        nargs="+",
        help=(
            "The job.id(s) of the job(s) to be cancelled. "
            "At least one job.id has to be provided."
        ),
        type=int,
        default=None,
    )
    cancel.set_defaults(func=ketchup.cancel)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument(
        "jobids",
        nargs="+",
        help=(
            "The job.id(s) of the job(s) to be snapshotted. "
            "At least one job.id has to be provided."
        ),
        type=int,
        default=None,
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
            type=int,
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
            "--yaml",
            "-y",
            help="Return output as a yaml.",
            action="store_true",
            default=False,
        )

    parse_args(parser, verbose, is_tomato=False)


def run_passata():
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
    stats = subparsers.add_parser("status")
    attrs = subparsers.add_parser("attrs")
    capbs = subparsers.add_parser("capabilities")
    const = subparsers.add_parser("constants")
    gattr = subparsers.add_parser("get")

    for p in [stats, attrs, capbs, gattr, const]:
        p.add_argument(
            "name",
            help=(
                "The Component.name of the component to be queried. "
                "At least one Component.name has to be provided."
            ),
            type=str,
        )
        p.add_argument(
            "--port",
            "-p",
            help="Port number of tomato's reply socket",
            default=DEFAULT_TOMATO_PORT,
            type=int,
        )
        p.add_argument(
            "--timeout",
            help="Timeout for the tomato command, in milliseconds",
            type=int,
            default=3000,
        )
        p.add_argument(
            "--yaml",
            "-y",
            help="Return output as a yaml.",
            action="store_true",
            default=False,
        )

    gattr.add_argument(
        "attrs",
        help="The attribute name(s) to be queried.",
        nargs="+",
    )

    stats.set_defaults(func=passata.status)
    attrs.set_defaults(func=passata.attrs)
    capbs.set_defaults(func=passata.capabilities)
    const.set_defaults(func=passata.constants)
    gattr.set_defaults(func=passata.get_attrs)

    parse_args(parser, verbose, is_tomato=False)
