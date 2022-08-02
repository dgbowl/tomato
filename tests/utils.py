import subprocess
import time
import psutil
import signal
import os
import logging
from typing import Callable

logger = logging.getLogger(__name__)

from tomato import dbhandler

def tomato_setup():
    logger.debug("In 'tomato_setup'.")
    cfg = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(["tomato", "-t", "-vv"], creationflags=cfg)
    p = psutil.Process(pid=proc.pid)
    while not os.path.exists("database.db"):
        time.sleep(0.1)
    conn, cur = dbhandler.get_db_conn("database.db", type="sqlite3")
    queue, state = False, False
    while not queue or not state:
        if not queue:
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='queue';"
            )
            queue = bool(len(cur.fetchall()))
        if not state:
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='state';"
            )
            state = bool(len(cur.fetchall()))
        time.sleep(0.1)
    conn.close()
    return proc, p


def ketchup_setup(casename, jobname):
    logger.debug("In 'ketchup_setup'.")
    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])
    args = ["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    subprocess.run(args)


def ketchup_loop(start, inter_func):
    inter_exec = False
    end = False
    logger.debug("In 'ketchup_loop'.")
    while True:
        dt = time.perf_counter() - start
        if end:
            logger.debug("Job complete in %d s. ", dt)
            break
        if dt > 120:
            logger.warning("Job took more than 120 s. Aborting...")
            break
        if not os.path.exists(os.path.join("Jobs", "1", "jobdata.log")):
            continue
        if inter_exec and inter_func is not None:
            logger.debug("Running 'inter_func()'")
            inter_func()
            inter_exec = False
        ret = subprocess.run(
            ["ketchup", "-t", "status", "1"],
            capture_output=True,
            text=True,
        )
        for line in ret.stdout.split("\n"):
            if line.startswith("status"):
                status = line.split("=")[1].strip()
                if status.startswith("c"):
                    end = True
                elif status.startswith("r"):
                    inter_exec = True
    return status


def ketchup_kill(proc, p):
    logger.debug("In 'ketchup_kill'.")
    for cp in p.children():
        cp.send_signal(signal.SIGTERM)
    proc.terminate()
    

def run_casename(
    casename: str, 
    jobname: str = None, 
    inter_func: Callable = None,
) -> str:
    proc, p = tomato_setup()
    ketchup_setup(casename, jobname)
    status = ketchup_loop(time.perf_counter(), inter_func)
    ketchup_kill(proc, p)
    return status


def cancel_job(jobid: int = 1):
    logger.debug("Running 'ketchup cancel'.")
    subprocess.run(["ketchup", "-t", "cancel", f"{jobid}", "-vv"])


def snapshot_job(jobid: int = 1):
    logger.debug("Running 'ketchup snapshot'.")
    subprocess.run(["ketchup", "-t", "snapshot", f"{jobid}", "-vv"])


def search_job(jobname: str = "$MATCH"):
    logger.debug("Running 'ketchup search'.")
    ret = subprocess.run(
        ["ketchup", "-t", "search", jobname, "-vv"],
        capture_output=True,
        text=True,
    )
    for line in ret.stdout.split("\n"):
        if "jobname" in line:
            assert jobname in line.split(":")[-1].strip()
        elif "jobid" in line:
            assert line.split(":")[-1].strip() == "1"
        elif "status" in line:
            assert line.split(":")[-1].strip() == "r"