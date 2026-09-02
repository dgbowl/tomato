import logging
import os
import subprocess
import time

import psutil
import xarray as xr
import yaml

logger = logging.getLogger(__name__)


def run_casenames(
    casenames: list[str], jobnames: list[str | None], pipelines: list[str]
) -> None:
    for cn, jn, pip in zip(casenames, jobnames, pipelines):
        subprocess.run(
            ["tomato", "pipeline", "load", "-p", "12345", pip, cn],
            check=True,
        )
        subprocess.run(
            ["tomato", "pipeline", "ready", "-p", "12345", pip],
            check=True,
        )
        args = ["ketchup", "submit", "-p", "12345", f"{cn}.yml"]
        if jn is not None:
            args.append("--jobname")
            args.append(jn)
        subprocess.run(args, check=True)


def job_status(jobid):
    ret = subprocess.run(
        ["ketchup", "status", "-p", "12345", str(jobid)],
        capture_output=True,
        text=True,
        check=True,
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
            check=True,
        )
        logger.debug("\n" + ret.stdout)
        if "Success" in ret.stdout:
            return True
        time.sleep(0.1)
    return False


def wait_until_tomato_drivers(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "drivers", "-y", "-p", f"{port}"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug("\n" + ret.stdout)
        yml = yaml.safe_load(ret.stdout)
        for drv in yml["data"].values():
            if drv["port"] is None:
                break
        else:
            return True
        time.sleep(0.1)
    return False


def wait_until_tomato_components(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "components", "-y", "-p", f"{port}"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug("\n" + ret.stdout)
        yml = yaml.safe_load(ret.stdout)
        for cmp in yml["data"].values():
            if cmp["capabilities"] is None:
                break
        else:
            return True
        time.sleep(0.1)
    return False


def wait_until_tomato_stopped(port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["tomato", "status", "-p", f"{port}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "Failure" in ret.stdout:
            return True
        time.sleep(0.1)
    return False


def wait_until_ketchup_status(jobid: int, status: str, port: int, timeout: int):
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < (timeout / 1000):
        ret = subprocess.run(
            ["ketchup", "status", "-p", f"{port}", f"{jobid}"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"{ret.stdout=}")
        if f"[{status!r}]" in ret.stdout:
            return True
        time.sleep(0.1)
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
    if psutil.WINDOWS:
        for p in psutil.process_iter(["name", "cmdline"]):
            if "tomato-daemon" in p.info["name"] and f"{port}" in p.info["cmdline"]:
                procs += p.children()
                p.terminate()
                procs.append(p)
    elif psutil.POSIX:
        for p in psutil.process_iter(["name", "cmdline"]):
            if "tomato-daemon" in p.info["name"] and f"{port}" in p.info["cmdline"]:
                p.terminate()
                procs.append(p)
    gone, alive = psutil.wait_procs(procs, timeout=1)
    print(f"{gone=}")
    print(f"{alive=}")


def sync_files():
    if psutil.WINDOWS:
        time.sleep(1)
    elif psutil.POSIX:
        subprocess.run(["sync"], check=True)


def check_npoints_file(fn: str, npoints: dict[str, int]):
    sync_files()
    assert os.path.exists(fn)
    dt = xr.load_datatree(fn)
    assert "tomato_version" in dt.attrs
    assert "tomato_Job" in dt.attrs
    for group, points in npoints.items():
        assert group in dt
        print(f"{dt[group]['uts'].size=}")
        assert dt[group]["uts"].size >= points
        print(f"{dt[group].attrs=}")
        assert "tomato_Component" in dt[group].attrs
