import sqlite3
from typing import Callable
from datetime import datetime, timezone
import os
import logging
log = logging.getLogger(__name__)


def get_queue_func(dbpath, type="sqlite3") -> Callable:
    if type == "sqlite3":
        sql = sqlite3
    else:
        raise RuntimeError(f"database type '{type}' unsupported")
    if not os.path.exists(dbpath):
        conn = sql.connect(dbpath)
        conn.close()
    log.debug(f"attempting to load the 'queue' database at '{dbpath}'")
    conn = sql.connect(dbpath)
    cur = conn.cursor()
    log.debug(f"attempting to find table 'queue' in '{dbpath}'")
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='queue';"
    )
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'queue' present at '{dbpath}'")
    else:
        log.warning(f"creating a new {type} 'queue' table at '{dbpath}'")
        conn = sql.connect(dbpath)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS queue ("
            "    jobid INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    payload TEXT NOT NULL,"
            "    status TEXT NOT NULL,"
            "    submitted_at TEXT NOT NULL,"
            "    executed_at TEXT,"
            "    completed_at TEXT"
            ");"
        )
        conn.close()
    return lambda: sql.connect(dbpath)


def get_state_func(dbpath, type="sqlite3") -> Callable:
    if type == "sqlite3":
        sql = sqlite3
    else:
        raise RuntimeError(f"database type '{type}' unsupported")

    if not os.path.exists(dbpath):
        conn = sql.connect(dbpath)
        conn.close()
    
    log.debug(f"attempting to load the 'state' database at '{dbpath}'")
    conn = sql.connect(dbpath)
    cur = conn.cursor()
    log.debug(f"attempting to find table 'state' in '{dbpath}'")
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='state';"
    )
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'state' present at '{dbpath}'")
    else:
        sql_create_queue_table = textwrap.dedent("""\
            """)
        log.warning(f"creating a new {type} 'state' table at '{dbpath}'")
        conn = sql.connect(dbpath)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS state ("
            "    pipeline TEXT PRIMARY KEY,"
            "    sampleid TEXT,"
            "    ready INTEGER NOT NULL,"
            "    jobid INTEGER,"
            "    pid INTEGER,"
            "    FOREIGN KEY (jobid) REFERENCES queue (jobid)"
            "    );"
        )
        conn.close()
    return lambda: sql.connect(dbpath)


def job_set_status(queue: Callable, st: str, jobid: int) -> None:
    conn = queue()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queue SET status = '{st}' WHERE jobid = {jobid};"
    )
    conn.commit()
    conn.close()


def job_set_time(queue: Callable, tcol: str, jobid: int) -> None:
    ts = str(datetime.now(timezone.utc))
    conn = queue()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queue SET {tcol} = '{ts}' WHERE jobid = {jobid};"
    )
    conn.commit()
    conn.close()


def job_get_all(queue: Callable) -> list[tuple]:
    conn = queue()
    cur = conn.cursor()
    cur.execute(
        "SELECT jobid, payload, status FROM queue;"
    )
    ret = cur.fetchall()
    conn.close()
    return ret


def pipeline_reset_job(state: Callable, pip: str, ready: bool = False) -> None:
    conn = state()
    cur = conn.cursor()
    r = int(ready)
    cur.execute(
        f"UPDATE state SET pid = NULL, jobid = NULL, ready = {r} "
        f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def pipeline_assign_job(state: Callable, pip: str, jobid: int, pid: int) -> None:
    conn = state()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE state SET pid = {pid}, jobid = {jobid}, ready = 0 "
        f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def pipeline_get_running(state: Callable) -> list[tuple]:
    conn = state()
    cur = conn.cursor()
    cur.execute(
        "SELECT pipeline, jobid, pid FROM state WHERE pid IS NOT NULL;"
    )
    ret = cur.fetchall()
    conn.close()
    return ret


def queue_payload(queue: Callable, pstr: str) -> None:
    conn = queue()
    cur = conn.cursor()
    log.info(f"inserting a new job into 'state'")
    cur.execute(
        "INSERT INTO queue (payload, status, submitted_at)"
        "VALUES (?, ?, ?);",
        (pstr, 'q', str(datetime.now(timezone.utc)))
    )
    conn.commit()
    conn.close()