import subprocess
import time
import psutil
import signal
import os
import logging

logger = logging.getLogger(__name__)


def run_casename(
    casename: str, jobname: str = None, inter_func: callable = None
) -> str:
    cfg = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(["tomato", "-t", "-vv"], creationflags=cfg)
    p = psutil.Process(pid=proc.pid)
    while not os.path.exists("database.db"):
        time.sleep(1)

    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])
    args = ["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    subprocess.run(args)
    
    while not os.path.exists(os.path.join("Jobs", "1", "jobdata.log")):
        time.sleep(1)

    inter_exec = False
    start = time.perf_counter()
    end = False
    while True:
        time.sleep(0.1)
        dt = time.perf_counter() - start
        if inter_exec and inter_func is not None:
            logger.debug("Running 'inter_func()'")
            inter_func()
            inter_exec = False
        if end:
            logger.debug("Job complete in %d s. ", dt)
            break
        if dt > 120:
            logger.warning("Job took more than 120 s. Aborting...")
            break
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
    for cp in p.children():
        cp.send_signal(signal.SIGTERM)
    proc.terminate()
    return status


def cancel_job(jobid: int = 1):
    logger.debug("Running 'ketchup cancel'.")
    subprocess.run(["ketchup", "-t", "cancel", f"{jobid}", "-vv"])


def snapshot_job(jobid: int = 1):
    logger.debug("Running 'ketchup snapshot'.")
    subprocess.run(["ketchup", "-t", "snapshot", f"{jobid}", "-vv"])
