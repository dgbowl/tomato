import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def connect_db(dbpath: str | Path):
    head = Path(dbpath).parent
    if not head.exists():
        logger.warning("making local data folder '%s'", head)
        os.makedirs(head)
    conn = sqlite3.connect(dbpath)
    cur = conn.cursor()
    return conn, cur


def setup_db(dbpath: str | Path) -> None:
    user_version = 3
    conn, cur = connect_db(dbpath)
    logger.debug("attempting to find table 'queue' in '%s'", dbpath)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue';")
    exists = bool(len(cur.fetchall()))
    if exists:
        logger.debug("table 'queue' present at '%s'", dbpath)
        cur.execute("PRAGMA user_version;")
        curr_version = cur.fetchone()[0]
        assert curr_version == user_version
        # Below is an example of upgrading databases to new user_version:
        while curr_version < user_version:
            if curr_version == 1:
                logger.info("upgrading sqlite db from version 1 to 2")
                cur.execute(
                    "ALTER TABLE queue RENAME COLUMN executed_at TO connected_at;"
                )
                cur.execute("ALTER TABLE queue ADD COLUMN launched_at TEXT;")
                cur.execute("UPDATE queue SET launched_at = connected_at;")
                cur.execute("PRAGMA user_version = 2;")
                conn.commit()
            if curr_version == 2:
                logger.info("upgrading sqlite db from version 2 to 3")
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS pipelines ("
                    "    name TEXT PRIMARY KEY,"
                    "    ready INTEGER NOT NULL,"
                    "    jobid INTEGER,"
                    "    sampleid TEXT"
                    ");",
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS drivers ("
                    "    name TEXT PRIMARY KEY,"
                    "    port INTEGER,"
                    "    pid INTEGER,"
                    "    version TEXT,"
                    "    spawn_time REAL DEFAULT 0.0,"
                    "    spawn_count INTEGER DEFAULT 0,"
                    "    heartbeat_time REAL DEFAULT 0.0"
                    ");",
                )
                cur.execute("PRAGMA user_version = 3;")
                conn.commit()
            cur.execute("PRAGMA user_version;")
            curr_version = cur.fetchone()[0]
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
            "    launched_at TEXT,"
            "    connected_at TEXT,"
            "    completed_at TEXT,"
            "    jobpath TEXT,"
            "    respath TEXT,"
            "    snappath TEXT"
            ");",
        )
        logger.info("creating a new sqlite3 'pipelines' table at '%s'", dbpath)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS pipelines ("
            "    name TEXT PRIMARY KEY,"
            "    ready INTEGER NOT NULL,"
            "    jobid INTEGER,"
            "    sampleid TEXT"
            ");",
        )
        logger.info("creating a new sqlite3 'drivers' table at '%s'", dbpath)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS drivers ("
            "    name TEXT PRIMARY KEY,"
            "    port INTEGER,"
            "    pid INTEGER,"
            "    version TEXT,"
            "    spawn_time REAL DEFAULT 0.0,"
            "    spawn_count INTEGER DEFAULT 0,"
            "    heartbeat_time REAL DEFAULT 0.0"
            ");",
        )
        cur.execute(f"PRAGMA user_version = {user_version};")
        conn.commit()
    conn.close()
