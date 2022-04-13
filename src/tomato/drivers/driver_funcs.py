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
    driver: str, command: str, address: str, channel: int, **kwargs: dict
) -> Any:
    m = importlib.import_module(f"tomato.drivers.{driver}")
    func = getattr(m, command)
    return func(address, channel, **kwargs)


def data_poller(
    driver: str, 
    address: str, 
    channel: int, 
    device: str, 
    root: str, 
    logqueue: multiprocessing.Queue, 
    configurer: Callable,
    kwargs: dict
) -> None:
    
    configurer(logqueue)
    log = logging.getLogger()

    pollrate = kwargs.pop("pollrate", 10)
    verbose = bool(kwargs.pop("verbose", 0))
    cont = True
    while cont:
        ts, nrows, data = driver_api(driver, "get_data", address, channel, **kwargs)
        while nrows > 0:
            isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            isots = isots.replace(":", "")
            fn = os.path.join(root, f"{device}_{isots}_data.json")
            log.debug(f"'{device}': found {nrows} data rows, writing into '{fn}'")
            with open(fn, "w") as of:
                json.dump(data, of)
            ts, nrows, data = driver_api(driver, "get_data", address, channel, **kwargs)

        ts, done, metadata = driver_api(
            driver, "get_status", address, channel, **kwargs
        )
        if verbose:
            isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            isots = isots.replace(":", "")
            fn = os.path.join(root, f"{device}_{isots}_status.json")
            log.debug(f"'{device}': writing status info into '{fn}'")
            with open(fn, "w") as of:
                json.dump(metadata, of)
    
        if done:
            cont = False
        else:
            time.sleep(pollrate)
    log.info(f"'{device}': rejoining main thread")




def driver_worker(
    settings: dict, 
    pipeline: dict, 
    payload: dict, 
    jobid: int,
    logfile: str
) -> None:
    
    log = logging.getLogger(__name__)
    log.debug("setting up queue and listener")
    queue = multiprocessing.Queue(-1)
    listener = multiprocessing.Process(
        target=log_listener, 
        args=(queue, log_listener_config, logfile)
    )
    listener.start()


    root = os.path.join(settings["queue"]["storage"], str(jobid))
    jobs = []
    for vi, v in enumerate(pipeline["devices"]):
        log.info(f"device id: {vi+1} out of {len(pipeline['devices'])}")
        log.info(f"processing device '{v['tag']}' of type '{v['driver']}'") 
        drv, addr, ch, tag = v["driver"], v["address"], v["channel"], v["tag"]
        dpar = settings["drivers"].get(drv, {})
        pl = payload["method"][tag]
        smpl = payload["sample"]

        log.debug(f"getting status of {vi+1}")
        ts, ready, metadata = driver_api(drv, "get_status", addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."

        log.debug(f"starting payload on {vi+1}")
        start_ts = driver_api(drv, "start_job", addr, ch, **dpar, payload=pl, **smpl)
        metadata["uts"] = start_ts

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
        log.info(f"starting data poller on {vi+1}: every {kwargs['pollrate']}s")
        p = multiprocessing.Process(
            name=f"data_poller_{jobid}_{tag}",
            target=data_poller,
            args=(drv, addr, ch, tag, root, queue, log_worker_config, kwargs),
        )
        jobs.append(p)
        p.start()

    log.info("waiting for data pollers to join")
    for p in jobs:
        p.join()
    
    log.debug("quitting log listener")
    queue.put_nowait(None)
    listener.join()
    return
