import sqlite3
import logging
import os
import pickle
from tomato.models import Job
from datetime import datetime, timezone

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


def job_to_db(job: Job, dbpath: str) -> int:
    conn, cur = connect_jobdb(dbpath)
    if job.id is None:
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
    else:
        cur.execute(
            "UPDATE queue "
            "SET payload = ?, jobname = ?, pid = ?, status = ?, "
            "submitted_at = ?, executed_at = ?, completed_at = ?, "
            "jobpath = ?, respath = ?, snappath = ?"
            "WHERE id = ?",
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
                job.id,
            ),
        )
    conn.commit()
    cur.execute(f"SELECT id FROM queue WHERE submitted_at = '{job.submitted_at}';")
    ret = cur.fetchone()[0]
    conn.close()
    return ret


def db_to_job(id: int, dbpath: str) -> Job:
    conn, cur = connect_jobdb(dbpath)
    cur.execute("SELECT * FROM queue WHERE id = ?;", (id,))
    columns = [i[0] for i in cur.description]
    data = cur.fetchone()
    conn.close()
    j = Job(**{k: v for k, v in zip(columns, data)})
    return j


if __name__ == "__main__":
    dbpath = "testdb.sqlite"
    jobdb_setup(dbpath)
    payload = {
        "version": "0.2",
        "sample": {"name": "counter_1_0.1"},
        "method": [
            {"device": "counter", "technique": "count", "time": 1.0, "delay": 0.1},
        ],
        "tomato": {"verbosity": "DEBUG"},
    }
    job = Job(payload=payload, submitted_at=str(datetime.now(timezone.utc)))
    print(job)
    id = job_to_db(job, dbpath)
    print(db_to_job(id, dbpath))
    # print(pickle.dumps(payload))
    # print(job)
    # j = db_to_job(1, dbpath)
    # print(j)
    # j.status = "c"
    # print(j)
    # job_to_db(j, dbpath)
    # print(db_to_job(1, dbpath))
