import zmq
import logging
import time
import multiprocessing
import argparse
import json
import os
import psutil
import subprocess
from .. import dbhandler
from ..daemon.main import _find_matching_pipelines, _pipeline_ready_sample, _kill_tomato_job

logger = logging.getLogger(__name__)


def run_passata():
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
    port_rep = rep.bind(f"tcp://127.0.0.1:{args.port}")

    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    status = "bootstrap"
    settings = {}
    pipelines = {}

    while True:
        socks = dict(poller.poll(0))
        if rep in socks:
            msg = rep.recv_json()
            assert "cmd" in msg
            cmd = msg["cmd"]
            if cmd == "stop":
                status = "stop"
                msg = dict(status=status)
            elif cmd == "setup":
                settings = msg.get("settings", settings)
                pipelines = msg.get("pipelines", pipelines)
                if status == "bootstrap":
                    status = "running"
                msg = dict(status=status, pipelines=pipelines)
            elif cmd == "status":
                msg = dict(status=status)
            rep.send_json(msg)

        ## Former main loop - split into job and pipeline managers
        if status == "running":
            qup = settings["queue"]["path"]
            qut = settings["queue"]["type"]
            stp = settings["state"]["path"]
            stt = settings["state"]["type"]

            # check existing PIDs in state
            ret = dbhandler.pipeline_get_running(stp, type=stt)
            for pip, jobid, pid in ret:
                logger.debug(f"checking PID of running job '{jobid}'")
                if (
                    psutil.pid_exists(pid)
                    and "tomato_job" in psutil.Process(pid).name()
                ):
                    logger.debug(f"PID of running job '{jobid}' found")
                    _, _, st, _, _, _ = dbhandler.job_get_info(qup, jobid, type=qut)
                    print(f"{jobid=} {st=}")
                    if st in {"rd"}:
                        logger.warning(f"cancelling a running job {jobid} with pid {pid}")
                        proc = psutil.Process(pid=pid)
                        logger.debug(f"{proc=}")
                        _kill_tomato_job(proc)
                        logger.info(f"setting job {jobid} to status 'cd'")
                        dbhandler.job_set_status(qup, "cd", jobid, type=qut)
                else:
                    logger.debug(f"PID of running job '{jobid}' not found")
                    dbhandler.pipeline_reset_job(stp, pip, False, type=stt)
                    dbhandler.job_set_status(qup, "ce", jobid, type=qut)
                    dbhandler.job_set_time(qup, "completed_at", jobid, type=qut)

            # check queued jobs in queue, get their payloads and any matching pipelines
            ret = dbhandler.job_get_all_queued(qup, type=qut)
            matched_pips = {}
            payloads = {}
            jobids = []
            for jobid, _, strpl, st in ret:
                payload = json.loads(strpl)
                payloads[jobid] = payload
                jobids.append(jobid)
                if st == "q":
                    logger.info(f"checking whether job '{jobid}' can ever be matched")
                matched_pips[jobid] = _find_matching_pipelines(
                    pipelines, payload["method"]
                )
                if len(matched_pips[jobid]) > 0 and st != "qw":
                    dbhandler.job_set_status(qup, "qw", jobid, type=qut)

            # iterate over sorted queued jobs and submit if pipeline with is loaded & ready
            for jobid in sorted(jobids):
                payload = payloads[jobid]
                logger.debug(f"checking whether job '{jobid}' can be queued")
                for pip in matched_pips[jobid]:
                    pipinfo = dbhandler.pipeline_get_info(stp, pip["name"], type=stt)
                    if not _pipeline_ready_sample(pipinfo, payload["sample"]):
                        continue
                    logger.info(f"queueing job '{jobid}' on pipeline '{pip['name']}'")
                    dbhandler.pipeline_reset_job(stp, pip["name"], False, type=stt)
                    args = {
                        "settings": settings,
                        "pipeline": pip,
                        "payload": payload,
                        "jobid": jobid,
                    }
                    root = os.path.join(settings["queue"]["storage"], str(jobid))
                    os.makedirs(root)
                    jpath = os.path.join(root, "jobdata.json")
                    with open(jpath, "w") as of:
                        json.dump(args, of, indent=1)
                    if psutil.WINDOWS:
                        cfs = subprocess.CREATE_NO_WINDOW
                        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                        subprocess.Popen(
                            ["tomato_job", str(jpath)],
                            creationflags=cfs,
                        )
                    elif psutil.POSIX:
                        subprocess.Popen(
                            ["tomato_job", str(jpath)],
                            start_new_session=True,
                        )
                    break
        if status == "stop":
            break
        else:
            time.sleep(settings.get("main loop", 0.1))
