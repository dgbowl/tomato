from typing import Any
from importlib import metadata
import importlib
import argparse
import time
import multiprocessing
import os
import json
from datetime import datetime, timezone
import logging
import psutil
import zmq
from pathlib import Path

from .logger_funcs import log_listener_config, log_listener, log_worker_config
from . import yadg_funcs

import xarray as xr
from threading import Thread
from tomato.models import Component, Device, Driver


def tomato_job() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "--port",
        help="Port on which tomato-daemon is listening.",
        default=1234,
        type=int,
    )
    parser.add_argument(
        "jobfile",
        type=Path,
        help="Path to a ketchup-processed payload json file.",
    )
    args = parser.parse_args()

    with args.jobfile.open() as infile:
        jsdata = json.load(infile)
    payload = jsdata["payload"]
    pip = jsdata["pipeline"]["name"]
    jobid = jsdata["job"]["id"]
    jobpath = Path(jsdata["job"]["path"]).resolve()

    logfile = jobpath / f"job-{jobid}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s:%(levelname)-8s:%(processName)s:%(message)s",
        handlers=[logging.FileHandler(logfile, mode="a"), logging.StreamHandler()],
    )
    logger = logging.getLogger(__name__)

    tomato = payload.get("tomato", {})
    verbosity = tomato.get("verbosity", "INFO")
    loglevel = logging._checkLevel(verbosity)
    logger.debug("setting logger verbosity to '%s'", verbosity)
    logger.setLevel(loglevel)

    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()

    logger.debug(f"assigning job {jobid} with pid {pid} into pipeline {pip!r}")
    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{args.port}")
    params = dict(pid=pid, status="r", executed_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(dict(cmd="job", id=jobid, params=params))
    req.recv_pyobj()

    logger.info("handing off to 'job_worker'")
    logger.info("==============================")
    ret = job_worker(context, args.port, payload["method"], pip, jobpath)
    logger.info("==============================")

    output = tomato["output"]
    prefix = f"results.{jobid}" if output["prefix"] is None else output["prefix"]
    path = Path(output["path"])
    logger.debug(f"output folder is {path}")
    if path.exists():
        assert path.is_dir()
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(path)

    if ret is None:
        logger.info("job finished successfully, setting status to 'c'")
        params = dict(status="c", completed_at=str(datetime.now(timezone.utc)))
        req.send_pyobj(dict(cmd="job", id=jobid, params=params))
        ret = req.recv_pyobj()
    else:
        logger.info("job was terminated, status should be 'cd'")
        logger.info("handing off to 'driver_reset'")
        logger.info("==============================")
        #driver_reset(pip)
        logger.info("==============================")
        ready = False
    if not ret.success:
        logger.error("could not set job status")
        return 1
    logger.info(f"resetting pipeline {pip}")
    params = dict(jobid=None, ready=ready)
    req.send_pyobj(dict(cmd="pipeline", pipeline=pip, params=params))
    ret = req.recv_pyobj()
    if not ret.success:
        logger.error("could not reset pipeline")
        return 1


def data_to_netcdf(data: list, path: Path):
    vars = {}
    for ii, item in enumerate(data):
        for k, v in item.items():
            if k not in vars:
                vars[k] = [None] * ii
            vars[k].append(v)

    data_vars = {}
    for k, v in vars.items():
        if "uts" in vars:
            data_vars[k] = ("uts", v, None)
        else:
            data_vars[k] = (None, v, None)

    ds = xr.Dataset(data_vars=data_vars)
    if path.exists():
        oldds = xr.load_dataset(path)
        ds = xr.concat([oldds, ds], dim="uts")
    ds.to_netcdf(path)


def job_thread(
    context: zmq.Context,
    tasks: list,
    component: Component,
    device: Device,
    driver: Driver,
    jobpath: Path,
):
    sender = f"{__name__}.job_thread"
    logger = logging.getLogger(sender)
    logger.debug(f"in job thread of {component.role!r}")

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{driver.port}")
    logger.debug(f"connected")
    kwargs = dict(address=component.address, channel=component.channel)

    datapath = jobpath / f"{component.role}.nc"

    for task in tasks:
        logger.debug(f"{task=}")
        while True:
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
            if ret.success and ret.msg == "ready":
                break

        req.send_pyobj(dict(cmd="task_start", params={**task, **kwargs}))
        ret = req.recv_pyobj()
        logger.debug(f"{ret=}")

        t0 = time.perf_counter()
        while True:
            tN = time.perf_counter()
            if tN - t0 > device.pollrate:
                req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
                ret = req.recv_pyobj()
                data_to_netcdf(ret.data, datapath)
                t0 += device.pollrate
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
            if ret.success and ret.msg == "ready":
                break
            time.sleep(device.pollrate / 10)
        req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
        ret = req.recv_pyobj()
        data_to_netcdf(ret.data, datapath)


def job_worker(
    context: zmq.Context,
    port: int,
    method: dict,
    pipname: str,
    jobpath: Path,
) -> None:
    sender = f"{__name__}.job_worker"
    logger = logging.getLogger(sender)

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")

    req.send_pyobj(dict(cmd="status", with_data=True, sender=sender))
    daemon = req.recv_pyobj().data

    pipeline = daemon.pips[pipname]
    logger.debug(f"{pipeline=}")

    # collate steps by role
    plan = {}
    for step in method:
        if step["device"] not in plan:
            plan[step["device"]] = []
        task = {k: v for k, v in step.items()}
        del task["device"]
        task["task"] = task.pop("technique")
        plan[step["device"]].append(task)
    logger.debug(f"{plan=}")

    # distribute plan into threads
    threads = {}
    for role, tasks in plan.items():
        component = pipeline.devs[role]
        logger.debug(f"{component=}")
        device = daemon.devs[component.name]
        logger.debug(f"{device=}")
        driver = daemon.drvs[device.driver]
        logger.debug(f"{driver=}")
        threads[role] = Thread(
            target=job_thread,
            args=(context, tasks, component, device, driver, jobpath),
        )
        threads[role].do_run = True
        threads[role].start()

    # wait until threads join
    while True:
        joined = [not thread.is_alive() for thread in threads.values()]
        logger.debug(f"{joined=}")
        if all(joined):
            break
        else:
            time.sleep(1)