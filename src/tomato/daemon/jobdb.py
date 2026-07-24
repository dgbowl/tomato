"""
**tomato.daemon.jobdb**: the sqlite database for jobs in tomato
---------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import logging
import pickle

from tomato.daemon.db import connect_db
from tomato.models import Job

logger = logging.getLogger(__name__)


def insert_job(job: Job, dbpath: str) -> Job:
    conn, cur = connect_db(dbpath)
    cur.execute(
        "INSERT INTO queue (payload, jobname, pid, status, submitted_at, "
        "launched_at, connected_at, completed_at, jobpath, respath, snappath)"
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        (
            pickle.dumps(job.payload),
            job.jobname,
            job.pid,
            job.status,
            job.submitted_at,
            job.launched_at,
            job.connected_at,
            job.completed_at,
            job.jobpath,
            job.respath,
            job.snappath,
        ),
    )
    conn.commit()
    cur.execute(f"SELECT id FROM queue WHERE submitted_at = '{job.submitted_at}';")
    id = cur.fetchone()[0]
    conn.close()
    return get_job_id(id, dbpath)


def update_job_id(id: int, params: dict, dbpath: str) -> Job:
    conn, cur = connect_db(dbpath)
    for k, v in params.items():
        cur.execute(f"UPDATE queue SET {k} = ? WHERE id = {id};", (v,))
    conn.commit()
    conn.close()
    return get_job_id(id, dbpath)


def get_job_id(id: int, dbpath: str) -> Job:
    conn, cur = connect_db(dbpath)
    cur.execute("SELECT * FROM queue WHERE id = ?;", (id,))
    columns = [i[0] for i in cur.description]
    data = cur.fetchone()
    conn.close()
    j = Job(**{k: v for k, v in zip(columns, data)})
    return j


def get_jobs_where(where: str, dbpath: str) -> list[Job]:
    conn, cur = connect_db(dbpath)
    cur.execute(f"SELECT * FROM queue WHERE {where};")
    columns = [i[0] for i in cur.description]
    data = cur.fetchall()
    conn.close()
    jobs = []
    for row in data:
        jobs.append(Job(**{k: v for k, v in zip(columns, row)}))
    return jobs
