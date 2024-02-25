import time
import os
import logging
import zmq
from pathlib import Path
import xarray as xr

from multiprocessing import Process
from tomato.models import Component, Device, Driver


def merge_netcdfs(jobpath: Path, outpath: Path):
    fns = [fn for fn in os.listdir(jobpath) if fn.endswith(".nc")]
    datasets = [xr.load_dataset(jobpath / fn, engine="h5netcdf") for fn in fns]
    if len(datasets) > 0:
        ds = xr.concat(datasets, dim="uts")
        ds.to_netcdf(outpath, engine="h5netcdf")


def data_to_netcdf(ds: xr.Dataset, path: Path):
    if path.exists():
        oldds = xr.load_dataset(path, engine="h5netcdf")
        ds = xr.concat([oldds, ds], dim="uts")
    ds.to_netcdf(path, engine="h5netcdf")


def job_process(
    tasks: list,
    component: Component,
    device: Device,
    driver: Driver,
    jobpath: Path,
):
    sender = f"{__name__}.job_process"
    logger = logging.getLogger(sender)
    logger.debug(f"in job process of {component.role!r}")

    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{driver.port}")
    logger.debug(f"job process of {component.role!r} connected to tomato-daemon")

    kwargs = dict(address=component.address, channel=component.channel)

    datapath = jobpath / f"{component.role}.nc"
    logger.debug("distributing tasks:")
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
                if ret.success:
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
        if ret.success:
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
    processes = {}
    for role, tasks in plan.items():
        component = pipeline.devs[role]
        logger.debug(f"{component=}")
        device = daemon.devs[component.name]
        logger.debug(f"{device=}")
        driver = daemon.drvs[device.driver]
        logger.debug(f"{driver=}")
        processes[role] = Process(
            target=job_process,
            args=(tasks, component, device, driver, jobpath),
        )
        processes[role].start()

    # wait until threads join or we're killed
    while True:
        joined = [proc.is_alive() is False for proc in processes.values()]
        if all(joined):
            break
        else:
            time.sleep(1)
    logger.debug(f"{[proc.exitcode for proc in processes.values()]}")
    for proc in processes.values():
        if proc.exitcode != 0:
            return proc.exitcode
