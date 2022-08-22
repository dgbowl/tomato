import sqlite3
from datetime import datetime, timezone
import logging
import os

log = logging.getLogger(__name__)


def get_db_conn(
    dbpath: str,
    type: str = "sqlite3",
) -> tuple:
    if type == "sqlite3":
        sql = sqlite3
    else:
        raise RuntimeError(f"database type '{type}' unsupported")

    head, tail = os.path.split(dbpath)
    if head != "" and not os.path.exists(head):
        log.warning("making local data folder '%s'", head)
        os.makedirs(head)
    conn = sql.connect(dbpath)
    cur = conn.cursor()
    return conn, cur


def queue_setup(
    dbpath: str,
    type: str = "sqlite3",
) -> None:
    user_version = 1
    conn, cur = get_db_conn(dbpath, type)
    log.debug(f"attempting to find table 'queue' in '{dbpath}'")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue';")
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'queue' present at '{dbpath}'")
        conn, cur = get_db_conn(dbpath, type)
        cur.execute("PRAGMA user_version;")
        curr_version = cur.fetchone()[0]
        while curr_version < user_version:
            if curr_version == 0:
                log.info("upgrading table 'queue' from version 0 to 1")
                cur.execute("ALTER TABLE queue ADD COLUMN jobname TEXT;")
                cur.execute("PRAGMA user_version = 1;")
                conn.commit()
            cur.execute("PRAGMA user_version;")
            curr_version = cur.fetchone()[0]
    else:
        log.warning(f"creating a new {type} 'queue' table at '{dbpath}'")
        conn, cur = get_db_conn(dbpath, type)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS queue ("
            "    jobid INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    payload TEXT NOT NULL,"
            "    status TEXT NOT NULL,"
            "    submitted_at TEXT NOT NULL,"
            "    executed_at TEXT,"
            "    completed_at TEXT,"
            "    jobname TEXT"
            ");"
        )
        cur.execute(f"PRAGMA user_version = {user_version};")
        conn.commit()
        conn.close()


def state_setup(
    dbpath: str,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    log.debug(f"attempting to find table 'state' in '{dbpath}'")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='state';")
    exists = bool(len(cur.fetchall()))
    conn.close()
    if exists:
        log.debug(f"table 'state' present at '{dbpath}'")
    else:
        log.warning(f"creating a new {type} 'state' table at '{dbpath}'")
        conn, cur = get_db_conn(dbpath, type)
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
        conn.commit()
        conn.close()


def job_set_status(
    dbpath: str,
    st: str,
    jobid: int,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(f"UPDATE queue SET status = '{st}' WHERE jobid = {jobid};")
    conn.commit()
    conn.close()


def job_get_info(
    dbpath: str,
    jobid: int,
    type: str = "sqlite3",
) -> tuple:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        "SELECT jobname, payload, status, submitted_at, executed_at, completed_at "
        "FROM queue "
        f"WHERE jobid = {jobid};"
    )
    ret = cur.fetchone()
    conn.close()
    return ret


def job_set_time(
    dbpath: str,
    tcol: str,
    jobid: int,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    ts = str(datetime.now(timezone.utc))
    cur.execute(f"UPDATE queue SET {tcol} = '{ts}' WHERE jobid = {jobid};")
    conn.commit()
    conn.close()


def job_get_all_queued(
    dbpath: str,
    type: str = "sqlite3",
) -> list[tuple]:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        "SELECT jobid, jobname, payload, status "
        "FROM queue "
        f"WHERE status IN ('qw', 'q');"
    )
    ret = cur.fetchall()
    conn.close()
    return ret


def job_get_all(
    dbpath: str,
    type: str = "sqlite3",
) -> list[tuple]:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute("SELECT jobid, jobname, payload, status FROM queue;")
    ret = cur.fetchall()
    conn.close()
    return ret


def pipeline_reset_job(
    dbpath: str,
    pip: str,
    ready: bool = False,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    r = int(ready)
    cur.execute(
        f"UPDATE state SET pid = NULL, jobid = NULL, ready = {r} "
        f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def pipeline_assign_job(
    dbpath: str,
    pip: str,
    jobid: int,
    pid: int,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        f"UPDATE state SET pid = {pid}, jobid = {jobid}, ready = 0 "
        f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def pipeline_get_running(
    dbpath: str,
    type: str = "sqlite3",
) -> list[tuple]:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute("SELECT pipeline, jobid, pid FROM state WHERE pid IS NOT NULL;")
    ret = cur.fetchall()
    conn.close()
    return ret


def pipeline_get_all(
    dbpath: str,
    type: str = "sqlite3",
) -> list[tuple]:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute("SELECT pipeline FROM state;")
    ret = [i[0] for i in cur.fetchall()]
    conn.close()
    return ret


def pipeline_get_info(
    dbpath: str,
    pip: str,
    type: str = "sqlite3",
) -> tuple:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        f"SELECT sampleid, ready, jobid, pid FROM state WHERE pipeline='{pip}';"
    )
    ret = cur.fetchone()
    conn.close()
    return ret


def pipeline_remove(
    dbpath: str,
    pip: str,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    log.warning(f"deleting pipeline '{pip}' from 'state'")
    cur.execute(f"DELETE FROM state WHERE pipeline='{pip}';")
    conn.commit()
    conn.close()


def pipeline_insert(
    dbpath: str,
    pip: str,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    log.info(f"creating pipeline '{pip}' in 'state'")
    cur.execute(
        "INSERT INTO state (pipeline, sampleid, jobid, ready)" "VALUES (?, ?, ?, ?);",
        (pip, None, None, 0),
    )
    conn.commit()
    conn.close()


def pipeline_load_sample(
    dbpath: str,
    pip: str,
    sampleid: str,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        f"UPDATE state SET sampleid = '{sampleid}', ready = 0 "
        f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def pipeline_eject_sample(
    dbpath: str,
    pip: str,
    type: str = "sqlite3",
) -> None:
    conn, cur = get_db_conn(dbpath, type)
    cur.execute(
        f"UPDATE state SET sampleid = NULL, ready = 0 " f"WHERE pipeline = '{pip}';"
    )
    conn.commit()
    conn.close()


def queue_payload(
    dbpath: str,
    pstr: str,
    type: str = "sqlite3",
    jobname: str = None,
) -> tuple:
    conn, cur = get_db_conn(dbpath, type)
    log.info(f"inserting a new job into 'state'")
    submitted_at = str(datetime.now(timezone.utc))
    if jobname is None:
        cur.execute(
            "INSERT INTO queue (payload, status, submitted_at)" "VALUES (?, ?, ?);",
            (pstr, "q", submitted_at),
        )
    else:
        cur.execute(
            "INSERT INTO queue (payload, status, submitted_at, jobname)"
            "VALUES (?, ?, ?, ?);",
            (pstr, "q", submitted_at, str(jobname)),
        )
    conn.commit()
    cur.execute("SELECT jobid FROM queue " f"WHERE submitted_at = '{submitted_at}';")
    ret = cur.fetchone()[0]
    conn.close()
    return ret
