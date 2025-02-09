"""
**tomato.daemon.jobdb**: the sqlite database for jobs in tomato
---------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import sqlite3
import logging
import os
import pickle
from tomato.models import Job

logger = logging.getLogger(__name__)


def connect_jobdb(dbpath: str):
    head, tail = os.path.split(dbpath)
    if head != "" and not os.path.exists(head):
        logger.warning("making local data folder '%s'", head)
        os.makedirs(head)
    conn = sqlite3.connect(dbpath)
    cur = conn.cursor()
    return conn, cur


def jobdb_setup(dbpath: str) -> None:
    user_version = 1
    conn, cur = connect_jobdb(dbpath)
    logger.debug("attempting to find table 'queue' in '%s'", dbpath)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue';")
    exists = bool(len(cur.fetchall()))
    if exists:
        logger.debug("table 'queue' present at '%s'", dbpath)
        cur.execute("PRAGMA user_version;")
        curr_version = cur.fetchone()[0]
        assert curr_version == user_version
        # Below is an example of upgrading databases to new user_version:
        # while curr_version < user_version:
        #    if curr_version == 0:
        #        log.info("upgrading table 'queue' from version 0 to 1")
        #        cur.execute("ALTER TABLE queue ADD COLUMN jobname TEXT;")
        #        cur.execute("PRAGMA user_version = 1;")
        #        conn.commit()
        #    cur.execute("PRAGMA user_version;")
        #    curr_version = cur.fetchone()[0]
    else:
        logger.info("creating a new sqlite3 'queue' table at '%s'", dbpath)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS queue ("
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    payload BLOB NOT NULL,"
            "    jobname TEXT,"
            "    pid INTEGER,"
            "    status TEXT NOT NULL,"
            "    submitted_at TEXT NOT NULL,"
            "    executed_at TEXT,"
            "    completed_at TEXT,"
            "    jobpath TEXT,"
            "    respath TEXT,"
            "    snappath TEXT"
            ");",
        )
        cur.execute(f"PRAGMA user_version = {user_version};")
        conn.commit()
    conn.close()


def insert_job(job: Job, dbpath: str) -> int:
    conn, cur = connect_jobdb(dbpath)
    cur.execute(
        "INSERT INTO queue (payload, jobname, pid, status, submitted_at, "
        "executed_at, completed_at, jobpath, respath, snappath)"
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        (
            pickle.dumps(job.payload),
            job.jobname,
            job.pid,
            job.status,
            job.submitted_at,
            job.executed_at,
            job.completed_at,
            job.jobpath,
            job.respath,
            job.snappath,
        ),
    )
    conn.commit()
    cur.execute(f"SELECT id FROM queue WHERE submitted_at = '{job.submitted_at}';")
    ret = cur.fetchone()[0]
    conn.close()
    return ret


def update_job_id(id: int, params: dict, dbpath: str) -> Job:
    conn, cur = connect_jobdb(dbpath)
    for k, v in params.items():
        cur.execute(f"UPDATE queue SET {k} = ? WHERE id = {id};", (v,))
    conn.commit()
    conn.close()
    return get_job_id(id, dbpath)


def get_job_id(id: int, dbpath: str) -> Job:
    conn, cur = connect_jobdb(dbpath)
    cur.execute("SELECT * FROM queue WHERE id = ?;", (id,))
    columns = [i[0] for i in cur.description]
    data = cur.fetchone()
    conn.close()
    j = Job(**{k: v for k, v in zip(columns, data)})
    return j


def get_jobs_where(where: str, dbpath: str) -> list[Job]:
    conn, cur = connect_jobdb(dbpath)
    cur.execute(f"SELECT * FROM queue WHERE {where};")
    columns = [i[0] for i in cur.description]
    data = cur.fetchall()
    conn.close()
    jobs = []
    for row in data:
        jobs.append(Job(**{k: v for k, v in zip(columns, row)}))
    return jobs
