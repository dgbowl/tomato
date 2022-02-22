"""
Main module - executables for tomato.

"""
import argparse
import logging
log = logging.getLogger(__name__)
import appdirs
import os
import yaml
import json
import sqlite3
import textwrap
from importlib import metadata
from datetime import datetime, timezone
from typing import Callable

from . import daemon
from . import dbhandler
from . import setlib





def _get_sample(path: str, name: str) -> dict:
    with open(path, "r") as sf:
        samples = yaml.full_load(sf)
    return samples.get(name, None)


def _add_sample(path: str, name: str, params: dict) -> None:
    with open(path, "rw") as sf:
        samples = yaml.full_load(sf)
        samples[name] = params
        yaml.dump(samples, sf)

def _assign_sample(sampleid: str, pipeline: str) -> None:
    return

def sync_pipelines_to_state(
    pipelines: dict, 
    dbpath: str, 
    type: str = "sqlite3",
) -> None:
    pstate = dbhandler.pipeline_get_all(dbpath, type)
    print(pstate)
    for pip in pipelines.keys():
        log.debug(f"checking presence of pipeline '{pip}' in 'state'")
        if pip not in pstate:
            dbhandler.pipeline_insert(dbpath, pip, type)
    for pip in pstate:
        if pip not in pipelines:
            dbhandler.pipeline_remove(dbpath, pip, type)


def run_tomato():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity by one level."
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="Decrease verbosity by one level."
    )
    parser.add_argument(
        "-d",
        "--daemonize",
        action="store_true",
        default=False,
        help="Daemonize tomato."
    )
    args = parser.parse_args()
    loglevel = min(max(30 + 10 * (args.quiet - args.verbose), 10), 50)
    logging.basicConfig(level=loglevel)
    log.debug(f"loglevel set to '{logging._levelToName[loglevel]}'")

    dirs = appdirs.AppDirs("tomato", "dgbowl", version=metadata.version("tomato"))
    log.debug(f"local config folder is '{dirs.user_config_dir}'")
    log.debug(f"local data folder is '{dirs.user_data_dir}'")
    log.debug(f"local log folder is '{dirs.user_log_dir}'")

    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    pipelines = setlib.get_pipelines(settings["devices"]["path"])
    
    log.debug(f"setting up 'queue' table in '{settings['queue']['path']}'")
    dbhandler.queue_setup(
        settings["queue"]["path"], type = settings["queue"]["type"]
    )
    log.debug(f"setting up 'state' table in '{settings['queue']['path']}'")
    dbhandler.state_setup(
        settings["state"]["path"], type = settings["state"]["type"]
    )
    sync_pipelines_to_state(
        pipelines, settings["state"]["path"], type = settings["state"]["type"]
    )

    daemon.main_loop(settings, pipelines)


def run_ketchup():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity by one level."
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="Decrease verbosity by one level."
    )
    parser.add_argument(
        "jobfile",
        help="Job file to be submitted to queue."
    )
    args = parser.parse_args()
    loglevel = min(max(30 + 10 * (args.quiet - args.verbose), 10), 50)
    logging.basicConfig(level=loglevel)
    log.debug(f"loglevel set to '{logging._levelToName[loglevel]}'")

    dirs = appdirs.AppDirs("tomato", "dgbowl", version=metadata.version("tomato"))
    log.debug(f"local config folder is '{dirs.user_config_dir}'")
    log.debug(f"local data folder is '{dirs.user_data_dir}'")
    log.debug(f"local log folder is '{dirs.user_log_dir}'")

    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    qc = dbhandler.get_queue_func(
        settings["queue"]["path"], type = settings["queue"]["type"]
    )

    with open(args.jobfile, "r") as infile:
        payload = json.load(infile)
    pstr = json.dumps(payload)
    dbhandler.queue_payload(qc, pstr)
    