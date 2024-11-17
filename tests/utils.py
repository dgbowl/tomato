import subprocess
import time
import logging
import os
import psutil

logger = logging.getLogger(__name__)


def run_casenames(
    casenames: list[str], jobnames: list[str], pipelines: list[str]
) -> str:
    for cn, jn, pip in zip(casenames, jobnames, pipelines):
        subprocess.run(["tomato", "pipeline", "load", "-p", "12345", pip, cn])
        subprocess.run(["tomato", "pipeline", "ready", "-p", "12345", pip])
        args = ["ketchup", "submit", "-p", "12345", f"{cn}.yml"]
        if jn is not None:
            args.append("--jobname")
            args.append(jn)
        subprocess.run(args)


def job_status(jobid):
    ret = subprocess.run(
        ["ketchup", "status", "-p", "12345", str(jobid)],
        capture_output=True,
        text=True,
    )
    status = ret.stdout.split("'")[1]
    return status


def wait_until_tomato_running(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "-p", f"{port}"],
            capture_output=True,
            text=True,
        )
        if "Success" in ret.stdout:
            return True
        time.sleep(0.5)
    return False


def wait_until_tomato_stopped(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "-p", f"{port}"],
            capture_output=True,
            text=True,
        )
        if "Failure" in ret.stdout:
            return True
        time.sleep(0.5)
    return False


def wait_until_ketchup_status(jobid: int, status: str, port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["ketchup", "status", "-p", f"{port}", f"{jobid}"],
            capture_output=True,
            text=True,
        )
        if f"[{status!r}]" in ret.stdout:
            return True
        time.sleep(0.5)
    return False


def wait_until_pickle(jobid: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        files = os.listdir(os.path.join(os.getcwd(), "Jobs", f"{jobid}"))
        for file in files:
            if file.endswith(".pkl"):
                return True
        time.sleep(0.5)
    return False


def kill_tomato_daemon(port: int = 12345):
    procs = []
    for p in psutil.process_iter(["name", "cmdline"]):
        if "tomato-daemon" in p.info["name"] and f"{port}" in p.info["cmdline"]:
            for pc in p.children():
                if psutil.WINDOWS:
                    pc.terminate()
                    procs.append(p)
            p.terminate()
            procs.append(p)
    gone, alive = psutil.wait_procs(procs, timeout=3)
    print(f"{gone=}")
    print(f"{alive=}")
