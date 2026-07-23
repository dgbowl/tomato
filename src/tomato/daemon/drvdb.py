"""
**tomato.daemon.drvdb**: the sqlite database for drivers in tomato
--------------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import logging

from tomato.daemon.db import connect_db
from tomato.models import DrvState

logger = logging.getLogger(__name__)


def insert_drv(drv: DrvState, dbpath: str) -> DrvState | None:
    conn, cur = connect_db(dbpath)
    cur.execute(
        "INSERT INTO drivers (name, port, pid, version, "
        "spawn_time, spawn_count, heartbeat_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?);",
        (
            drv.name,
            drv.port,
            drv.pid,
            drv.version,
            drv.spawn_time,
            drv.spawn_count,
            drv.heartbeat_time,
        ),
    )
    conn.commit()
    return get_drv(drv.name, dbpath)


def update_drv(name: str, params: dict, dbpath: str) -> DrvState | None:
    conn, cur = connect_db(dbpath)
    for k, v in params.items():
        cur.execute(f"UPDATE drivers SET {k} = ? WHERE name = '{name}';", (v,))
    conn.commit()
    conn.close()
    return get_drv(name, dbpath)


def get_drv(name: str, dbpath: str) -> DrvState | None:
    conn, cur = connect_db(dbpath)
    cur.execute("SELECT * FROM drivers WHERE name = ?;", (name,))
    columns = [i[0] for i in cur.description]
    data = cur.fetchone()
    conn.close()
    if data is not None:
        return DrvState(**{k: v for k, v in zip(columns, data)})
    else:
        return None


def get_drvs_where(where: str, dbpath: str) -> list[DrvState]:
    conn, cur = connect_db(dbpath)
    cur.execute(f"SELECT * FROM drivers WHERE {where};")
    columns = [i[0] for i in cur.description]
    data = cur.fetchall()
    conn.close()
    rets = []
    for row in data:
        rets.append(DrvState(**{k: v for k, v in zip(columns, row)}))
    return rets


def del_drv(name: str, dbpath: str) -> DrvState | None:
    conn, cur = connect_db(dbpath)
    cur.execute(f"DELETE FROM drivers WHERE name = '{name}';", (name,))
    conn.commit()
    conn.close()
    return get_drv(name, dbpath)
