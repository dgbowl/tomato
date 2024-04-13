import subprocess
import time
import yaml
import logging

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
    yml = yaml.safe_load(ret.stdout)
    return yml


def wait_until_tomato_running(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "-p", f"{port}"],
            capture_output=True,
            text=True,
        )
        data = yaml.safe_load(ret.stdout)
        if data["success"]:
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
        data = yaml.safe_load(ret.stdout)
        if not data["success"]:
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
        data = yaml.safe_load(ret.stdout)["data"]
        if data[jobid]["status"] == status:
            return True
        time.sleep(0.5)
    return False
