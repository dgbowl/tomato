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


def tomato_job() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "--port",
        help="Path to a ketchup-processed payload json file.",
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
    pipeline = jsdata["pipeline"]
    devices = jsdata["devices"]
    job = jsdata["job"]

    pip = pipeline["name"]
    jobpath = Path(job["path"]).resolve()

    logfile = jobpath / f"job-{job['id']}.log"
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

    logger.debug(f"assigning job {job['id']} with pid '{pid}' into pipeline: {pip}")
    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{args.port}")
    params = dict(pid=pid, status="r", executed_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(dict(cmd="job", id=job["id"], params=params))
    req.recv_pyobj()

    logger.info("handing off to 'driver_worker'")
    logger.info("==============================")
    ret = driver_worker(
        devices, pipeline, payload, job["id"], jobpath, logfile, loglevel
    )
    logger.info("==============================")

    output = tomato["output"]
    prefix = f"results.{job['id']}" if output["prefix"] is None else output["prefix"]
    path = Path(output["path"])
    logger.debug(f"output folder is {path}")
    if path.exists():
        assert path.is_dir()
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(path)

    preset = yadg_funcs.get_yadg_preset(payload["method"], pipeline, devices)
    yadg_funcs.process_yadg_preset(
        preset=preset, path=path, prefix=prefix, jobdir=str(jobpath)
    )
    logger.debug("here")
    ready = tomato.get("unlock_when_done", False)
    if ret is None:
        logger.info("job finished successfully, setting status to 'c'")
        params = dict(status="c", completed_at=str(datetime.now(timezone.utc)))
        req.send_pyobj(dict(cmd="job", id=job["id"], params=params))
        ret = req.recv_pyobj()
    else:
        logger.info("job was terminated, status should be 'cd'")
        logger.info("handing off to 'driver_reset'")
        logger.info("==============================")
        driver_reset(pipeline)
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


def driver_api(
    driver: str,
    command: str,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    address: str,
    channel: int,
    **kwargs: dict,
) -> Any:
    m = importlib.import_module(f"tomato.drivers.{driver}")
    func = getattr(m, command)
    return func(address, channel, jobqueue, logger, **kwargs)


def data_poller(
    driver: str,
    jq: multiprocessing.Queue,
    lq: multiprocessing.Queue,
    address: str,
    channel: int,
    device: str,
    root: str,
    loglevel: int,
    kwargs: dict,
) -> None:
    log_worker_config(lq, loglevel)
    log = logging.getLogger()
    pollrate = kwargs.pop("pollrate", 10)
    log.debug(f"in 'data_poller', {pollrate=}")
    cont = True
    previous = None
    while cont:
        ts, done, _ = driver_api(
            driver, "get_status", jq, log, address, channel, **kwargs
        )
        ts, nrows, data = driver_api(
            driver, "get_data", jq, log, address, channel, **kwargs
        )
        data["previous"] = previous
        previous = data["current"]
        while nrows > 0:
            isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            isots = isots.replace(":", "")
            fn = os.path.join(root, f"{device}_{isots}_data.json")
            log.debug(f"found {nrows} data rows, writing into '{fn}'")
            with open(fn, "w") as of:
                json.dump(data, of)
            ts, nrows, data = driver_api(
                driver, "get_data", jq, log, address, channel, **kwargs
            )
            data["previous"] = previous
            previous = data["current"]
        if done:
            cont = False
        else:
            time.sleep(pollrate)
    log.info("rejoining main thread")
    return


def data_snapshot(
    devices: dict,
    method: dict,
    pipeline: dict,
    snapshot: dict,
    jobid: int,
    jobfolder: str,
    lq: multiprocessing.Queue,
    loglevel: int,
) -> None:
    log_worker_config(lq, loglevel)
    start = time.perf_counter()
    if snapshot["prefix"] is None:
        prefix = f"snapshot.{jobid}"
    else:
        prefix = snapshot["prefix"]
    preset = yadg_funcs.get_yadg_preset(method, pipeline, devices)
    while True:
        if time.perf_counter() - start > snapshot["frequency"]:
            yadg_funcs.process_yadg_preset(
                preset=preset,
                path=snapshot["path"],
                prefix=prefix,
                jobdir=jobfolder,
            )
            start = time.perf_counter()
        time.sleep(1)


def driver_worker(
    devices: dict,
    pipeline: dict,
    payload: dict,
    jobid: int,
    jobpath: Path,
    logfile: str,
    loglevel: int,
) -> None:
    jq = multiprocessing.Queue(maxsize=0)

    log = logging.getLogger(__name__)
    log.setLevel(loglevel)
    log.debug("starting 'log_listener'")
    lq = multiprocessing.Queue(maxsize=0)
    listener = multiprocessing.Process(
        target=log_listener,
        name="log_listener",
        args=(lq, log_listener_config, logfile),
    )
    listener.start()
    log.debug(f"started 'log_listener' on pid {listener.pid}")

    jobs = []
    print(f"{devices=}")
    print(f"{pipeline['devs']=}")
    for cname, comp in pipeline["devs"].items():
        dev = devices[cname]
        log.info(f"device id: {cname}")
        log.info(
            f"{cname}: processing device '{comp['role']}' of type '{dev['driver']}'"
        )
        drv, addr, ch, tag = (
            dev["driver"],
            dev["address"],
            comp["channel"],
            comp["role"],
        )
        dpar = dev["settings"]
        pl = [item for item in payload["method"] if item["device"] == comp["role"]]
        smpl = payload["sample"]

        log.debug(f"{cname}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", jq, log, addr, ch, **dpar)
        log.debug(f"{ready=}")
        assert ready, f"Failed: device '{tag}' is not ready."

        log.debug(f"{cname}: starting payload")
        start_ts = driver_api(
            drv, "start_job", jq, log, addr, ch, **dpar, payload=pl, **smpl
        )
        metadata["uts"] = start_ts

        log.debug(f"{cname}: writing initial status")
        with (jobpath / f"{tag}_status.json").open("w") as of:
            json.dump(metadata, of)
        kwargs = dpar
        kwargs.update({"pollrate": dev.get("pollrate", 10)})
        log.info(f"{cname}: starting 'data_poller': every {kwargs['pollrate']}s")
        p = multiprocessing.Process(
            name=f"data_poller_{jobid}_{tag}",
            target=data_poller,
            args=(drv, jq, lq, addr, ch, tag, jobpath, loglevel, kwargs),
        )
        jobs.append(p)
        p.start()
        log.info(f"{cname}: started 'data_poller' on pid {p.pid}")

    shot = payload.get("tomato", {}).get("snapshot", None)
    if shot is not None:
        log.info(f"starting 'data_snapshot': shot every {shot['frequency']}s")
        sp = multiprocessing.Process(
            name=f"data_snapshot_{jobid}",
            target=data_snapshot,
            args=(
                devices,
                payload["method"],
                pipeline,
                shot,
                jobid,
                str(jobpath),
                lq,
                loglevel,
            ),
        )
        sp.start()
        log.info(f"started 'data_snapshot' on pid {sp.pid}")

    log.info("waiting for all 'data_poller' jobs to join")
    log.info("------------------------------------------")
    ret = None
    for p in jobs:
        p.join()
        log.debug(f"{p=}")
        if p.exitcode == 0:
            log.info(f"'data_poller' with pid {p.pid} closed successfully")
        else:
            log.critical(f"'data_poller' with pid {p.pid} was terminated")
            ret = 1

    log.info("-----------------------")
    log.info("quitting 'log_listener'")
    if shot is not None:
        log.info("quitting 'data_snapshot'")
        sp.terminate()
    lq.put_nowait(None)
    listener.join()
    jq.close()
    return ret


def driver_reset(pipeline: dict) -> None:
    log = logging.getLogger(__name__)
    for vi, v in enumerate(pipeline["devices"]):
        log.info(f"device id: {vi+1} out of {len(pipeline['devices'])}")
        log.info(f"{vi+1}: processing device '{v['tag']}' of type '{v['driver']}'")
        drv, addr, ch, tag = v["driver"], v["address"], v["channel"], v["tag"]
        # dpar = settings["drivers"].get(drv, {})
        dpar = {}

        log.debug(f"{vi+1}: resetting device")
        driver_api(drv, "stop_job", None, log, addr, ch, **dpar)

        log.debug(f"{vi+1}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", None, log, addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."
