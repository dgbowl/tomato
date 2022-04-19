from typing import Any, Callable
import importlib
import time
import multiprocessing
import os
import json
from datetime import datetime, timezone
import logging

from .logger_funcs import log_listener_config, log_listener, log_worker_config


def driver_api(
    driver: str, 
    command: str, 
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    address: str, 
    channel: int, 
    **kwargs: dict
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
    kwargs: dict
) -> None:
    log_worker_config(lq)
    log = logging.getLogger()
    pollrate = kwargs.pop("pollrate", 10)
    verbose = bool(kwargs.pop("verbose", 0))
    log.debug(f"in 'data_poller', {pollrate=}")
    cont = True
    while cont:
        ts, done, metadata = driver_api(
            driver, "get_status", jq, log, address, channel, **kwargs
        )
        if verbose:
            isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            isots = isots.replace(":", "")
            fn = os.path.join(root, f"{device}_{isots}_status.json")
            log.debug(f"'writing status info into '{fn}'")
            with open(fn, "w") as of:
                json.dump(metadata, of)
        ts, nrows, data = driver_api(
            driver, "get_data", jq, log, address, channel, **kwargs
        )
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
        if done:
            cont = False
        else:
            time.sleep(pollrate)
    log.info(f"rejoining main thread")
    return


def driver_worker(
    settings: dict, 
    pipeline: dict, 
    payload: dict, 
    jobid: int,
    logfile: str
) -> None:

    jq = multiprocessing.Queue(maxsize=0)
    
    log = logging.getLogger(__name__)
    log.debug("starting 'log_listener'")
    lq = multiprocessing.Queue(maxsize=0)
    listener = multiprocessing.Process(
        target=log_listener,
        name="log_listener", 
        args=(lq, log_listener_config, logfile)
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
        pl = payload["method"][tag]
        smpl = payload["sample"]

        log.debug(f"{vi+1}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", jq, log, addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."

        log.debug(f"{vi+1}: starting payload")
        start_ts = driver_api(
            drv, "start_job", jq, log, addr, ch, **dpar, payload=pl, **smpl
        )
        metadata["uts"] = start_ts

        log.debug(f"{vi+1}: writing metadata")
        isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace(":", "")
        fn = os.path.join(root, f"{tag}_{isots}_status.json")
        with open(fn, "w") as of:
            json.dump(metadata, of)
        kwargs = dpar
        kwargs.update(
            {
                "pollrate": v.get("pollrate", 10),
                "verbose": v.get("verbose", 0),
            }
        )
        log.info(f"{vi+1}: starting 'data_poller': every {kwargs['pollrate']}s")
        p = multiprocessing.Process(
            name=f"data_poller_{jobid}_{tag}",
            target=data_poller,
            args=(drv, jq, lq, addr, ch, tag, root, kwargs),
        )
        jobs.append(p)
        p.start()
        log.info(f"{vi+1}: started 'data_poller' on pid {p.pid}")

    log.info("waiting for all 'data_poller' jobs to join")
    log.info("------------------------------------------")
    ret = None
    for p in jobs:
        p.join()
        if p.exitcode == 0:
            log.info(f"'data_poller' with pid {p.pid} closed successfully")
        else:
            log.critical(f"'data_poller' with pid {p.pid} was terminated")
            ret = 1
    
    log.info("-----------------------")
    log.info("quitting 'log_listener'")
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
        driver_api(drv, "stop_job", addr, ch, **dpar)

        log.debug(f"{vi+1}: getting status")
        ts, ready, metadata = driver_api(drv, "get_status", addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."

        