from typing import Any
import importlib
import time
import multiprocessing
import os
import json
from datetime import datetime, timezone
import logging

log = logging.getLogger(__name__)


def driver_api(
    driver: str, command: str, address: str, channel: int, **kwargs: dict
) -> Any:
    m = importlib.import_module(f"tomato.drivers.{driver}")
    func = getattr(m, command)
    return func(address, channel, **kwargs)


def data_poller(
    driver: str, address: str, channel: int, device: str, root: str, kwargs: dict
) -> None:
    pollrate = kwargs.pop("pollrate", 10)
    verbose = bool(kwargs.pop("verbose", 0))
    cont = True
    while cont:
        ts, nrows, data = driver_api(driver, "get_data", address, channel, **kwargs)
        while nrows > 0:
            isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            isots = isots.replace(":", "")
            fn = os.path.join(root, f"{device}_{isots}_data.json")
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
            with open(fn, "w") as of:
                json.dump(metadata, of)

        if done:
            cont = False
        else:
            time.sleep(pollrate)


def driver_worker(settings: dict, pipeline: dict, payload: dict, jobid: int) -> None:
    root = os.path.join(settings["queue"]["storage"], str(jobid))
    jobs = []
    for v in pipeline["devices"]:
        print(v)
        drv, addr, ch, tag = v["driver"], v["address"], v["channel"], v["tag"]
        dpar = settings["drivers"].get(drv, {})
        pl = payload["method"][tag]
        smpl = payload["sample"]

        log.debug(f"jobid {jobid}: getting status of device '{tag}'")
        ts, ready, metadata = driver_api(drv, "get_status", addr, ch, **dpar)
        assert ready, f"Failed: device '{tag}' is not ready."

        log.debug(f"jobid {jobid}: starting payload for device '{tag}'")
        start_ts = driver_api(drv, "start_job", addr, ch, **dpar, payload=pl, **smpl)
        metadata["uts"] = start_ts

        isots = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace(":", "")
        fn = os.path.join(root, f"{tag}_{isots}_status.json")
        with open(fn, "w") as of:
            json.dump(metadata, of)

        log.debug(f"jobid {jobid}: starting data polling for device '{tag}'")
        kwargs = dpar
        kwargs.update(
            {
                "pollrate": v.get("pollrate", 10),
                "verbose": v.get("verbose", 0),
            }
        )
        p = multiprocessing.Process(
            name=f"data_poller_{jobid}_{tag}",
            target=data_poller,
            args=(drv, addr, ch, tag, root, kwargs),
        )
        jobs.append(p)
        p.start()

    for p in jobs:
        p.join()
    return
