"""
Driver documentation goes here.
"""

from importlib import metadata
import argparse
import os
import json
from datetime import datetime, timezone
import logging
import psutil
import zmq
from pathlib import Path
from tomato.drivers.jobfuncs import job_worker, merge_netcdfs

TIMEOUT = 1000


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
    ready = payload["tomato"].get("unlock_when_done", False)
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
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    params = dict(pid=pid, status="r", executed_at=str(datetime.now(timezone.utc)))
    req.send_pyobj(dict(cmd="job", id=jobid, params=params))
    events = dict(poller.poll(TIMEOUT))
    if req in events:
        req.recv_pyobj()
    else:
        logger.warning(f"could not contact tomato-daemon in {TIMEOUT/1000} s")

    logger.info("handing off to 'job_worker'")
    logger.info("==============================")
    ret = job_worker(context, args.port, payload["method"], pip, jobpath)
    logger.info("==============================")

    output = tomato["output"]
    prefix = f"results.{jobid}" if output["prefix"] is None else output["prefix"]
    outpath = Path(output["path"])
    logger.debug(f"output folder is {outpath}")
    if outpath.exists():
        assert outpath.is_dir()
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(outpath)

    merge_netcdfs(jobpath, outpath / f"{prefix}.nc")

    if ret is None:
        logger.info("job finished successfully, attempting to set status to 'c'")
        params = dict(status="c", completed_at=str(datetime.now(timezone.utc)))
        req.send_pyobj(dict(cmd="job", id=jobid, params=params))
        events = dict(poller.poll(TIMEOUT))
        if req not in events:
            logger.warning(f"could not contact tomato-daemon in {TIMEOUT/1000} s")
            req.setsockopt(zmq.LINGER, 0)
            req.close()
            poller.unregister(req)
            req = context.socket(zmq.REQ)
            req.connect(f"tcp://127.0.0.1:{args.port}")
        else:
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
            if ret.success is False:
                logger.error("could not set job status for unknown reason")
                return 1
    else:
        logger.info("job was terminated, status should be 'cd'")
        logger.info("handing off to 'driver_reset'")
        logger.info("==============================")
        # driver_reset(pip)
        logger.info("==============================")
        ready = False
    logger.info(f"resetting pipeline {pip!r}")
    params = dict(jobid=None, ready=ready, name=pip)
    req.send_pyobj(dict(cmd="pipeline", params=params))
    events = dict(poller.poll(TIMEOUT))
    if req in events:
        ret = req.recv_pyobj()
        logger.debug(f"{ret=}")
        if not ret.success:
            logger.error(f"could not reset pipeline {pip!r}")
            return 1
    else:
        logger.error(f"could not contact tomato-daemon in {TIMEOUT/1000} s")
        return 1
    logger.info("exiting tomato-job")
