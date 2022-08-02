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
        time.sleep(0.1)
    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    args = ["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    subprocess.run(args)
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])

    inter_exec = True if inter_func is not None else False

    start = time.perf_counter()
    while True:
        ret = subprocess.run(
            ["ketchup", "-t", "status", "1"],
            capture_output=True,
            text=True,
        )
        end = False
        for line in ret.stdout.split("\n"):
            if line.startswith("status"):
                status = line.split("=")[1].strip()
                if status.startswith("c"):
                    end = True
                    break
                elif status.startswith("r") and inter_exec:
                    logger.debug("Running 'inter_exec()'")
                    inter_func()
                    inter_exec = False
        time.sleep(0.1)
        if end:
            dt = time.perf_counter() - start
            logger.debug("Job complete in %d s. ", dt)
            break
        if time.perf_counter() - start > 120:
            logger.warning("Job took more than 120 s. Aborting...")
            break

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
