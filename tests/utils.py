import subprocess
import time
import signal
import os
import yaml
import logging
from typing import Callable, Union, Sequence
import psutil
import zmq
from tomato import tomato, ketchup

logger = logging.getLogger(__name__)


def tomato_setup():
    cmd = ["tomato", "init", "--datadir", ".", "--appdir", "."]
    subprocess.Popen(cmd)
    cmd = ["tomato", "start", "-p", "12345", "--appdir", ".", "--logdir", "."]
    if psutil.WINDOWS:
        cfg = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(cmd, creationflags=cfg)
    elif psutil.POSIX:
        proc = subprocess.Popen(cmd, start_new_session=True)
    p = psutil.Process(pid=proc.pid)
    count = 0
    while True:
        ret = subprocess.run(
            ["tomato", "status", "--port", "12345"],
            capture_output=True,
            text=True,
        )
        ret = yaml.safe_load(ret.stdout)
        print(f"{ret=}")
        if ret["success"] and ret["data"]["status"] == "running":
            break
        else:
            time.sleep(0.1)
            count += 1
            assert count < 20
    return proc, p


def sample_setup(casename, jobname, pip="dummy-10"):
    logger.debug("In 'ketchup_setup'.")
    subprocess.run(
        ["tomato", "pipeline", "load", "-p", "12345", "--appdir", ".", pip, casename]
    )
    subprocess.run(["tomato", "pipeline", "ready", "-p", "12345", "--appdir", ".", pip])
    args = ["ketchup", "submit", "-p", "12345", "--appdir", ".", f"{casename}.yml"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    subprocess.run(args)


def ketchup_loop(start, inter_func):
    print("In ketchup_loop")
    inter_exec = None
    end = False
    while True:
        time.sleep(1)
        dt = time.perf_counter() - start
        if end:
            logger.debug("Job complete in %d s. ", dt)
            break
        if dt > 30:
            logger.warning("Job took more than 120 s. Aborting...")
            break
        if not os.path.exists(os.path.join("Jobs", "1", "jobdata.log")):
            continue
        if inter_exec and inter_func is not None:
            print("Running 'inter_func()'")
            inter_func()
            inter_exec = False
        ret = subprocess.run(
            [
                "ketchup",
                "status",
                "-p",
                "12345",
                "--appdir",
                ".",
                "--datadir",
                ".",
                "1",
            ],
            capture_output=True,
            text=True,
        )
        print(f"{ret.stdout}")
        yml = yaml.safe_load(f"{ret.stdout}")
        if yml["success"]:
            status = yml["data"][0]["status"]
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
    print("tomato_setup()")
    # proc, p = tomato_setup()
    if isinstance(casename, str):
        print("sample_setup()")
        sample_setup(casename, jobname)
    elif isinstance(casename, Sequence):
        pnames = ["dummy-10", "dummy-5"]
        for idx, tup in enumerate(zip(casename, jobname)):
            cn, jn = tup
            pn = pnames[idx]
            sample_setup(cn, jn, pip=pn)
    print("ketchup_loop()")
    status = ketchup_loop(time.perf_counter(), inter_func)
    print("ketchup_kill()")
    ketchup_kill(proc, p)
    return status


def cancel_job(jobid: int = 1):
    print("Running 'ketchup cancel'.")
    subprocess.run(["ketchup", "cancel", "-p", "12345", "--appdir", ".", str(jobid)])


def snapshot_job(jobid: int = 1):
    print("Running 'ketchup snapshot'.")
    subprocess.run(["ketchup", "snapshot", "-p", "12345", "--appdir", ".", f"{jobid}"])


def search_job(jobname: str = "$MATCH"):
    logger.debug("Running 'ketchup search'.")
    ret = subprocess.run(
        ["ketchup", "search", "-p", "12345", "--appdir", ".", jobname],
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


def run_casenames(
    casenames: list[str],
    jobnames: list[str],
    pipelines: list[str],
    inter_func: Callable = None,
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
        print(f"{data=}")
        time.sleep(timeout / 20000)
    return False


def wait_until_ketchup_status(
    jobid: int,
    status: str,
    port: int,
    timeout: int,
):
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
        print(f"{data=}")
        time.sleep(timeout / 20000)
    return False
