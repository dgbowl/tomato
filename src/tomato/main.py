"""
Main module - executables for tomato.

"""
import argparse
import logging
from re import S
log = logging.getLogger(__name__)
import appdirs
import os
import toml
import yaml
import json
import sqlite3
import textwrap
from importlib import metadata
from datetime import datetime, timezone
from typing import Callable

from .daemon import main_loop


def _get_settings(configpath: str, datapath: str) -> dict:
    settingsfile = os.path.join(configpath, "settings.toml")
    if not os.path.exists(settingsfile):
        log.warning(f"config file not present. Writing defaults to '{settingsfile}'")
        defaults = textwrap.dedent(f"""\
            # Default settings for tomato v{metadata.version('tomato')}
            # Generated on {str(datetime.now(timezone.utc))}
            [state]
            type = 'sqlite3'
            path = '{os.path.join(datapath, 'database.db')}'

            [queue]
            type = 'sqlite3'
            path = '{os.path.join(datapath, 'database.db')}'
            storage = '{os.path.join(datapath, 'Jobs')}'
            
            [samples]
            path = '{os.path.join(configpath, 'samples.yml')}'

            [devices]
            path = '{os.path.join(configpath, 'devices.toml')}'

            [drivers]
            [drivers.biologic]
            dllpath = 'C:\EC-Lab Development Package\EC-Lab Development Package\'
            """)
        if not os.path.exists(configpath):
            os.makedirs(configpath)
        with open(settingsfile, "w") as of:
            of.write(defaults)
    
    log.debug(f"loading tomato settings from '{settingsfile}'")
    settings = toml.load(settingsfile)
    
    return settings


def _get_pipelines(tomlpath: str) -> dict:
    log.debug(f"loading pipeline settings from '{tomlpath}'")
    settings = toml.load(tomlpath)
    ppls = {}
    for k, v in settings["pipelines"].items():
        for devname in v["add_device"].keys():
            if v["add_device"][devname]["channel"] == "each":
                chs = settings["devices"][devname]["channels"]
            else:
                chs = [v["add_device"][devname]["channel"]]
            for ch in chs:
                name = k + str(ch)
                data = {
                    "address": settings["devices"][devname]["address"],
                    "driver": settings["devices"][devname]["driver"],
                    "channel": ch,
                    "capabilities": settings["devices"][devname]["capabilities"]
                }
                ppls[name] = {v["add_device"][devname]["name"]: data}
    return ppls


def _get_queue(dbpath, type="sqlite3") -> Callable:
    if type == "sqlite3":
        sql = sqlite3
    else:
        raise RuntimeError(f"database type '{type}' unsupported")

    if not os.path.exists(dbpath):
        conn = sql.connect(dbpath)
        conn.close()
    
    log.debug(f"attempting to load the 'queue' database at '{dbpath}'")
    sql_check_queue_table = textwrap.dedent("""\
        SELECT name FROM sqlite_master WHERE type='table' AND name='queue';""")
    conn = sql.connect(dbpath)
    cur = conn.cursor()
    log.debug(f"attempting to find table 'queue' in '{dbpath}'")
    cur.execute(sql_check_queue_table)
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'queue' present at '{dbpath}'")
    else:
        sql_create_queue_table = textwrap.dedent("""\
            CREATE TABLE IF NOT EXISTS queue (
                jobid INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                executed_at TEXT,
                completed_at TEXT
                );""")
        log.warning(f"creating a new {type} 'queue' table at '{dbpath}'")
        conn = sql.connect(dbpath)
        cur = conn.cursor()
        cur.execute(sql_create_queue_table)
        conn.close()
    return lambda: sql.connect(dbpath)


def _get_state(dbpath, type="sqlite3") -> Callable:
    if type == "sqlite3":
        sql = sqlite3
    else:
        raise RuntimeError(f"database type '{type}' unsupported")

    if not os.path.exists(dbpath):
        conn = sql.connect(dbpath)
        conn.close()
    
    log.debug(f"attempting to load the 'state' database at '{dbpath}'")
    sql_check_queue_table = textwrap.dedent("""\
        SELECT name FROM sqlite_master WHERE type='table' AND name='state';""")
    conn = sql.connect(dbpath)
    cur = conn.cursor()
    log.debug(f"attempting to find table 'state' in '{dbpath}'")
    cur.execute(sql_check_queue_table)
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'state' present at '{dbpath}'")
    else:
        sql_create_queue_table = textwrap.dedent("""\
            CREATE TABLE IF NOT EXISTS state (
                pipeline TEXT PRIMARY KEY,
                sampleid TEXT,
                ready INTEGER NOT NULL,
                jobid INTEGER,
                pid INTEGER,
                FOREIGN KEY (jobid) REFERENCES queue (jobid)
                );""")
        log.warning(f"creating a new {type} 'state' table at '{dbpath}'")
        conn = sql.connect(dbpath)
        cur = conn.cursor()
        cur.execute(sql_create_queue_table)
        conn.close()
    return lambda: sql.connect(dbpath)


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


def _sql_queue_payload(queue: Callable, pstr: str) -> None:
    conn = queue()
    cur = conn.cursor()
    log.info(f"inserting a new job into 'state'")
    sql_insert_job = textwrap.dedent(f"""\
        INSERT INTO queue (payload, status, submitted_at)
        VALUES (?, ?, ?)
        """)
    print(pstr)
    cur.execute(sql_insert_job, (pstr, 'q', str(datetime.now(timezone.utc))))
    conn.commit()
    conn.close()



def _pipelines_to_state(pipelines: dict, state: Callable) -> None:
    conn = state()
    cur = conn.cursor()
    for k in pipelines.keys():
        log.info(f"checking presence of pipeline '{k}' in 'state'")
        sql_query_pipeline = f"""SELECT * FROM state WHERE pipeline='{k}'"""
        cur.execute(sql_query_pipeline)
        ret = cur.fetchall()
        if len(ret) == 0:
            log.info(f"inserting pipeline '{k}' into 'state'")
            sql_insert_pipeline = textwrap.dedent(f"""\
                INSERT INTO state (pipeline, sampleid, jobid, ready)
                VALUES (?, ?, ?, ?);""")
            cur.execute(sql_insert_pipeline, (k, None, None, 0))
            conn.commit()
    conn.close()


def run_daemon():
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

    settings = _get_settings(dirs.user_config_dir, dirs.user_data_dir)
    pipelines = _get_pipelines(settings["devices"]["path"])
    qc = _get_queue(settings["queue"]["path"], type = settings["queue"]["type"])
    sc = _get_state(settings["state"]["path"], type = settings["state"]["type"])
    
    _pipelines_to_state(pipelines, sc)

    main_loop(settings, pipelines, qc, sc)


def run_qsub():
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

    settings = _get_settings(dirs.user_config_dir, dirs.user_data_dir)
    qc = _get_queue(settings["queue"]["path"], type = settings["queue"]["type"])

    with open(args.jobfile, "r") as infile:
        payload = json.load(infile)
    pstr = json.dumps(payload)
    _sql_queue_payload(qc, pstr)
    