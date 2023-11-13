import os
import subprocess
import logging
import time
import argparse
import json

import zmq
import psutil

from tomato.models import Pipeline, Reply
from .. import dbhandler

from .main import (
    _find_matching_pipelines,
    _pipeline_ready_sample,
    _kill_tomato_job,
)

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


def run_daemon():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=1234,
    )
    args = parser.parse_args()

    context = zmq.Context()
    rep = context.socket(zmq.REP)
    rep.bind(f"tcp://127.0.0.1:{args.port}")

    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    status = "bootstrap"
    settings = {}
    pipelines = {}

    while True:
        socks = dict(poller.poll(100))
        print(f"{socks=}")
        if rep in socks:
            msg = rep.recv_pyobj()
            print(f"{msg=}")
            assert "cmd" in msg
            cmd = msg["cmd"]
            if cmd == "stop":
                status = "stop"
                msg = Reply(success=True, msg=status)
            elif cmd == "setup":
                settings = msg.get("settings", settings)
                newpips = {p["name"]: Pipeline(**p) for p in msg.get("pipelines", {})}
                pipelines = merge_pipelines(pipelines, newpips)
                if status == "bootstrap":
                    status = "running"
                msg = Reply(
                    success=True, msg=status, data = [pip for pip in pipelines.values()]
                )
            elif cmd == "pipeline":
                pname = msg.get("pipeline")
                params = msg.get("params", {})
                for k, v in params.items():
                    setattr(pipelines[pname], k, v)
                msg = Reply(success=True, msg=status, data = pipelines[pname])
            elif cmd == "status":
                msg = Reply(
                    success=True, msg=status, data = [pip for pip in pipelines.values()]
                )
            print(f"{msg=}")
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
                        proc = psutil.Process(pid=pip.pid)
                        _kill_tomato_job(proc)
                        dbhandler.job_set_status(qup, "cd", pip.jobid, type=qut)
                else:
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
        # else:
        #    time.sleep(settings.get("main loop", 0.5))
