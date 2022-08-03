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

from tomato.dbhandler.sqlite import pipeline_assign_job

from .logger_funcs import log_listener_config, log_listener, log_worker_config
from . import yadg_funcs
from .. import dbhandler


def tomato_job() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "jobfile",
        help="Path to a ketchup-processed payload json file.",
        default=None,
    )
    args = parser.parse_args()

    jobfolder, _ = os.path.split(os.path.abspath(args.jobfile))
    logfile = args.jobfile.replace(".json", ".log")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s:%(levelname)-8s:%(processName)s:%(message)s",
        handlers=[logging.FileHandler(logfile, mode="a"), logging.StreamHandler()],
    )
    logger = logging.getLogger(__name__)

    logger.info("attempting to load jobfile '%s'", args.jobfile)
    with open(args.jobfile, "r") as infile:
        jsdata = json.load(infile)

    logger.debug("parsing data from jobfile")
    jobid = jsdata["jobid"]
    settings = jsdata["settings"]
    queue = settings["queue"]
    state = settings["state"]
    payload = jsdata["payload"]
    tomato = payload.get("tomato", {})
    pipeline = jsdata["pipeline"]
    pip = pipeline["name"]

    verbosity = tomato.get("verbosity", "INFO")
    loglevel = logging._checkLevel(verbosity)
    logger.debug("setting logger verbosity to '%s'", verbosity)
    logger.setLevel(loglevel)

    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()

    logger.debug(f"assigning job '{jobid}' on pid '{pid}' into pipeline '{pip}'")
    dbhandler.pipeline_assign_job(state["path"], pip, jobid, pid, type=state["type"])
    dbhandler.job_set_status(queue["path"], "r", jobid, type=queue["type"])
    dbhandler.job_set_time(queue["path"], "executed_at", jobid, type=queue["type"])

    logger.info("handing off to 'driver_worker'")
    logger.info("==============================")
    ret = driver_worker(
        settings, pipeline, payload, jobid, jobfolder, logfile, loglevel
    )

    logger.info("==============================")

    output = tomato["output"]
    prefix = f"results.{jobid}" if output["prefix"] is None else output["prefix"]
    path = output["path"]
    logger.debug("output path is '%s'", path)
    if os.path.exists(path):
        logger.debug("path exists, making sure it's a folder")
        assert os.path.isdir(path)
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(path)

    preset = yadg_funcs.get_yadg_preset(payload["method"], pipeline)
    yadg_funcs.process_yadg_preset(
        preset=preset, path=path, prefix=prefix, jobdir=jobfolder
    )

    ready = tomato.get("unlock_when_done", False)
    if ret is None:
        logger.info("job finished successfully, setting status to 'c'")
        dbhandler.job_set_status(queue["path"], "c", jobid, type=queue["type"])
    else:
        logger.info("job was terminated, setting status to 'cd'")
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
        logger.info("handing off to 'driver_reset'")
        logger.info("==============================")
        driver_reset(settings, pipeline)
        logger.info("==============================")
        ready = False

    logger.debug(f"setting pipeline '{pip}' as '{'ready' if ready else 'not ready'}'")
    dbhandler.pipeline_reset_job(state["path"], pip, ready, type=state["type"])
    dbhandler.job_set_time(queue["path"], "completed_at", jobid, type=queue["type"])


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
    log.info(f"rejoining main thread")
    return


def data_snapshot(
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
    preset = yadg_funcs.get_yadg_preset(method, pipeline)
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
    settings: dict,
    pipeline: dict,
    payload: dict,
    jobid: int,
    jobfolder: str,
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

    root = os.path.join(settings["queue"]["storage"], str(jobid))
    jobs = []
    for vi, v in enumerate(pipeline["devices"]):
        log.info(f"device id: {vi+1} out of {len(pipeline['devices'])}")
        log.info(f"{vi+1}: processing device '{v['tag']}' of type '{v['driver']}'")
        drv, addr, ch, tag = v["driver"], v["address"], v["channel"], v["tag"]
        dpar = settings["drivers"].get(drv, {})
        pl = [item for item in payload["method"] if item["device"] == v["tag"]]
        smpl = payload["sample"]

        log.debug(f"{vi+1}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", jq, log, addr, ch, **dpar)
        log.debug(f"{ready=}")
        assert ready, f"Failed: device '{tag}' is not ready."

        log.debug(f"{vi+1}: starting payload")
        start_ts = driver_api(
            drv, "start_job", jq, log, addr, ch, **dpar, payload=pl, **smpl
        )
        metadata["uts"] = start_ts

        log.debug(f"{vi+1}: writing initial status")
        fn = os.path.join(root, f"{tag}_status.json")
        with open(fn, "w") as of:
            json.dump(metadata, of)
        kwargs = dpar
        kwargs.update({"pollrate": v.get("pollrate", 10)})
        log.info(f"{vi+1}: starting 'data_poller': every {kwargs['pollrate']}s")
        p = multiprocessing.Process(
            name=f"data_poller_{jobid}_{tag}",
            target=data_poller,
            args=(drv, jq, lq, addr, ch, tag, root, loglevel, kwargs),
        )
        jobs.append(p)
        p.start()
        log.info(f"{vi+1}: started 'data_poller' on pid {p.pid}")

    shot = payload.get("tomato", {}).get("snapshot", None)
    if shot is not None:
        log.info(f"starting 'data_snapshot': shot every {shot['frequency']}s")
        sp = multiprocessing.Process(
            name=f"data_snapshot_{jobid}",
            target=data_snapshot,
            args=(payload["method"], pipeline, shot, jobid, jobfolder, lq, loglevel),
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


def driver_reset(
    settings: dict,
    pipeline: dict,
) -> None:
    log = logging.getLogger(__name__)
    for vi, v in enumerate(pipeline["devices"]):
        log.info(f"device id: {vi+1} out of {len(pipeline['devices'])}")
        log.info(f"{vi+1}: processing device '{v['tag']}' of type '{v['driver']}'")
        drv, addr, ch, tag = v["driver"], v["address"], v["channel"], v["tag"]
        dpar = settings["drivers"].get(drv, {})

        log.debug(f"{vi+1}: resetting device")
        driver_api(drv, "stop_job", None, log, addr, ch, **dpar)

        log.debug(f"{vi+1}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", None, log, addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."
