"""
**tomato.daemon.pipdb**: the sqlite database for pipelines in tomato
--------------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import logging

from tomato.daemon.db import connect_db
from tomato.models import PipState

logger = logging.getLogger(__name__)


def insert_pip(pip: PipState, dbpath: str) -> PipState | None:
    conn, cur = connect_db(dbpath)
    cur.execute(
        "INSERT INTO pipelines (name, ready, jobid, sampleid) VALUES (?, ?, ?, ?);",
        (pip.name, pip.ready, pip.jobid, pip.sampleid),
    )
    conn.commit()
    return get_pip(pip.name, dbpath)


def update_pip(name: str, params: dict, dbpath: str) -> PipState | None:
    conn, cur = connect_db(dbpath)
    for k, v in params.items():
        cur.execute(f"UPDATE pipelines SET {k} = ? WHERE name = '{name}';", (v,))
    conn.commit()
    conn.close()
    return get_pip(name, dbpath)


def get_pip(name: str, dbpath: str) -> PipState | None:
    conn, cur = connect_db(dbpath)
    cur.execute("SELECT * FROM pipelines WHERE name = ?;", (name,))
    columns = [i[0] for i in cur.description]
    data = cur.fetchone()
    conn.close()
    if data is not None:
        return PipState(**{k: v for k, v in zip(columns, data)})
    else:
        return None


def get_pips_where(where: str, dbpath: str) -> list[PipState]:
    conn, cur = connect_db(dbpath)
    cur.execute(f"SELECT * FROM pipelines WHERE {where};")
    columns = [i[0] for i in cur.description]
    data = cur.fetchall()
    conn.close()
    rets = []
    for row in data:
        rets.append(PipState(**{k: v for k, v in zip(columns, row)}))
    return rets
