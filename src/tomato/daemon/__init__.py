"""
**tomato.daemon**: module of functions comprising the tomato daemon
-------------------------------------------------------------------
.. codeauthor:: 
    Peter Kraus
"""
import os
import subprocess
import logging
import time
import argparse
import json
from pathlib import Path

import zmq
import psutil

from tomato.models import Pipeline, Reply
from tomato import dbhandler


logger = logging.getLogger(__name__)


def merge_pipelines(
    cur: dict[str, Pipeline], new: dict[str, Pipeline]
) -> dict[str, Pipeline]:
    ret = {}

    for pname, pip in cur.items():
        if pname not in new:
            if pip.jobid is not None:
                ret[pname] = pip
        else:
            if pip == new[pname]:
                ret[pname] = pip
            elif pip.jobid is None:
                ret[pname] = new[pname]
    for pname, pip in new.items():
        if pname not in cur:
            ret[pname] = pip
    return ret


def find_matching_pipelines(pipelines: dict, method: list[dict]) -> list[str]:
    print(f"{pipelines=}")
    print(f"{method=}")
    req_names = set([item["device"] for item in method])
    req_capabs = set([item["technique"] for item in method])

    candidates = []
    for pip in pipelines.values():
        dnames = set([device.tag for device in pip.devices])
        if req_names.intersection(dnames) == req_names:
            candidates.append(pip)

    matched = []
    for cd in candidates:
        capabs = []
        for device in cd.devices:
            capabs += device.capabilities
        if req_capabs.intersection(set(capabs)) == req_capabs:
            matched.append(cd)
    print(f"{matched=}")
    return matched


def kill_tomato_job(proc):
    pc = proc.children()
    logger.warning(
        "killing proc: name='%s', pid=%d, children=%d", proc.name(), proc.pid, len(pc)
    )
    if psutil.WINDOWS:
        for proc in pc:
            if proc.name() in {"conhost.exe"}:
                continue
            ppc = proc.children()
            for proc in ppc:
                try:
                    proc.terminate()
                except psutil.NoSuchProcess:
                    logger.warning(
                        "dead proc: name='%s', pid=%d", proc.name(), proc.pid
                    )
                    continue
            gone, alive = psutil.wait_procs(ppc, timeout=1)
    elif psutil.POSIX:
        for proc in pc:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                logger.warning("dead proc: name='%s', pid=%d", proc.name(), proc.pid)
                continue
        gone, alive = psutil.wait_procs(pc, timeout=1)


def run_daemon():
    """ """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=1234,
    )
    parser.add_argument(
        "--verbosity",
        type=int,
        default=logging.INFO,
    )
    parser.add_argument(
        "--logdir",
        type=str,
        default=str(Path.cwd()),
    )
    args = parser.parse_args()

    logger = logging.getLogger(f"{__name__}.run_daemon")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(Path(args.logdir) / f"daemon_{args.port}.log")
    fh.setLevel(args.verbosity)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info(f"logging set up with verbosity {args.verbosity}")

    context = zmq.Context()
    rep = context.socket(zmq.REP)
    logger.debug(f"binding zmq.REP socket on port {args.port}")
    rep.bind(f"tcp://127.0.0.1:{args.port}")

    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    status = "bootstrap"
    settings = {}
    pipelines = {}

    logger.debug(f"entering main loop")
    while True:
        socks = dict(poller.poll(100))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug(f"received {msg=}")
            if "cmd" not in msg:
                logger.error(f"received msg without cmd: {msg=}")
                rep.send_pyobj(
                    Reply(success=False, msg="received msg without cmd", data=msg)
                )
                continue
            cmd = msg["cmd"]
            if cmd == "stop":
                status = "stop"
                logger.critical(f"stopping tomato daemon")
                msg = Reply(success=True, msg=status)
            elif cmd == "setup":
                settings = msg.get("settings", settings)
                newpips = {p["name"]: Pipeline(**p) for p in msg.get("pipelines", {})}
                pipelines = merge_pipelines(pipelines, newpips)
                if status == "bootstrap":
                    logger.info(
                        f"tomato daemon setup successful with pipelines: {list(pipelines.keys())}"
                    )
                    status = "running"
                else:
                    logger.info(
                        f"tomato daemon reload successful with pipelines: {list(pipelines.keys())}"
                    )
                msg = Reply(
                    success=True, msg=status, data=[pip for pip in pipelines.values()]
                )
            elif cmd == "pipeline":
                pname = msg.get("pipeline")
                params = msg.get("params", {})
                for k, v in params.items():
                    logger.info(f"setting {pname}.{k} to {v}")
                    setattr(pipelines[pname], k, v)
                msg = Reply(success=True, msg=status, data=pipelines[pname])
            elif cmd == "status":
                msg = Reply(
                    success=True, msg=status, data=[pip for pip in pipelines.values()]
                )
            logger.debug(f"reply with {msg=}")
            rep.send_pyobj(msg)

        # Former main loop - split into job and pipeline managers
        if status == "running":
            qup = settings["queue"]["path"]
            qut = settings["queue"]["type"]

            # check existing PIDs in state
            running = [pip for pip in pipelines.values() if pip.jobid is not None]

            for pip in running:
                if pip.pid is not None and psutil.pid_exists(pip.pid):
                    ret = dbhandler.job_get_info(qup, pip.jobid, type=qut)
                    st = ret[2]
                    if st == "rd":
                        logger.warning(
                            f"job {pip.jobid} with pid {pip.pid} has been scheduled for termination"
                        )
                        proc = psutil.Process(pid=pip.pid)
                        kill_tomato_job(proc)
                        logger.debug(
                            f"job {pip.jobid} with pid {pip.pid} has been terminated successfully"
                        )
                        dbhandler.job_set_status(qup, "cd", pip.jobid, type=qut)
                else:
                    logging.warning(
                        f"the pid {pip.pid} associated with job {pip.jobid} has not been found"
                    )
                    dbhandler.job_set_status(qup, "ce", pip.jobid, type=qut)
                    dbhandler.job_set_time(qup, "completed_at", pip.jobid, type=qut)
                    pip.pid = None
                    pip.jobid = None
                    pip.ready = False

            # check queued jobs in queue, get their payloads and any matching pipelines
            ret = dbhandler.job_get_all_queued(qup, type=qut)
            matched_pips = {}
            payloads = {}
            jobids = []
            for jobid, _, strpl, st in ret:
                payload = json.loads(strpl)
                payloads[jobid] = payload
                jobids.append(jobid)
                matched_pips[jobid] = find_matching_pipelines(
                    pipelines, payload["method"]
                )
                if len(matched_pips[jobid]) > 0 and st != "qw":
                    logger.info(
                        f"job {jobid} can be queued onto pipelines: "
                        f"{[pip.name for pip in matched_pips[jobid]]}"
                    )
                    dbhandler.job_set_status(qup, "qw", jobid, type=qut)
            # iterate over sorted queued jobs and submit if pipeline with is loaded & ready
            for jobid in sorted(jobids):
                payload = payloads[jobid]
                for pip in matched_pips[jobid]:
                    if not pip.ready:
                        continue
                    elif pip.sampleid != payload["sample"]["name"]:
                        continue
                    pip.ready = False
                    jobargs = {
                        "settings": settings,
                        "pipeline": pip.dict(),
                        "payload": payload,
                        "jobid": jobid,
                    }
                    root = os.path.join(settings["queue"]["storage"], str(jobid))
                    os.makedirs(root)
                    jpath = os.path.join(root, "jobdata.json")
                    with open(jpath, "w", encoding="utf=8") as of:
                        json.dump(jobargs, of, indent=1)
                    logger.info(
                        f"launching job {jobid} on pipeline {pip.name} with job path {jpath}"
                    )
                    if psutil.WINDOWS:
                        cfs = subprocess.CREATE_NO_WINDOW
                        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                        subprocess.Popen(
                            ["tomato_job", "--port", str(args.port), str(jpath)],
                            creationflags=cfs,
                        )
                    elif psutil.POSIX:
                        subprocess.Popen(
                            ["tomato_job", "--port", str(args.port), str(jpath)],
                            start_new_session=True,
                        )
                    break
        if status == "stop":
            break
