import subprocess
import time
import psutil
import signal
import os
import yaml
import logging
from typing import Callable, Union, Sequence

logger = logging.getLogger(__name__)

from tomato import dbhandler


def tomato_setup():
    logger.debug("In 'tomato_setup'.")
    logger.debug("Running 'tomato init'")
    cmd = ["tomato", "init", "--datadir", ".", "--appdir", ".", "-vv"]
    subprocess.Popen(cmd)
    logger.debug("Running 'tomato start'")
    cmd = ["tomato", "start", "-p", "12345", "--appdir", ".", "--datadir", ".", "-vv"]
    if psutil.WINDOWS:
        cfg = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(cmd, creationflags=cfg)
    elif psutil.POSIX:
        proc = subprocess.Popen(cmd, start_new_session=True)
    logger.debug("Waiting for database.db")
    p = psutil.Process(pid=proc.pid)
    while not os.path.exists("database.db"):
        time.sleep(0.1)
    conn, cur = dbhandler.get_db_conn("database.db", type="sqlite3")
    queue, state = False, False
    while not queue or not state:
        if not queue:
            cur.execute(
                "SELECT name FROM sqlite_master " "WHERE type='table' AND name='queue';"
            )
            queue = bool(len(cur.fetchall()))
        if not state:
            cur.execute(
                "SELECT name FROM sqlite_master " "WHERE type='table' AND name='state';"
            )
            state = bool(len(cur.fetchall()))
        time.sleep(0.1)
    conn.close()
    return proc, p


def ketchup_setup(casename, jobname, pip="dummy-10"):
    logger.debug("In 'ketchup_setup'.")
    subprocess.run(["ketchup", "-t", "load", casename, pip, "-vv"])
    subprocess.run(["ketchup", "-t", "ready", pip, "-vv"])
    args = ["ketchup", "-t", "submit", f"{casename}.yml", "-vv"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    print(args)
    subprocess.run(args)


def ketchup_loop(start, inter_func):
    inter_exec = None
    end = False
    logger.debug("In 'ketchup_loop'.")
    while True:
        time.sleep(1)
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
        yml = yaml.safe_load(ret.stdout)
        assert len(yml) == 1
        status = yml[0]["status"]
        if status.startswith("c"):
            end = True
        elif status.startswith("r") and inter_exec is None:
            inter_exec = True
    return status


def ketchup_kill(proc, p):
    logger.debug("In 'ketchup_kill'.")
    for cp in p.children():
        cp.send_signal(signal.SIGTERM)
    proc.terminate()


def run_casename(
    casename: Union[str, list[str]],
    jobname: Union[str, list[str]] = None,
    inter_func: Callable = None,
) -> str:
    proc, p = tomato_setup()
    if isinstance(casename, str):
        ketchup_setup(casename, jobname)
    elif isinstance(casename, Sequence):
        pnames = ["dummy-10", "dummy-5"]
        for idx, tup in enumerate(zip(casename, jobname)):
            cn, jn = tup
            pn = pnames[idx]
            print(f"{cn=}, {jn=}, {pn=}")
            ketchup_setup(cn, jn, pip=pn)
    status = ketchup_loop(time.perf_counter(), inter_func)
    ketchup_kill(proc, p)
    subprocess.run(["tomato", "stop", "-p", "12345"])
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


if __name__ == "__main__":
    logging.basicConfig(level=50)
    status = run_casename("dummy_random_1_0.1")
    print(f"{status=}")


def old():

    print("tomato_setup():")
    ret = tomato_setup()
    print(f"{ret=}")
    
    print("ketchup_setup():")
    ret = ketchup_setup("dummy_random_1_0.1", "test")
    print(f"{ret=}")

    print("tomato stop")
    subprocess.run(["tomato", "stop", "-p", "12345"])
