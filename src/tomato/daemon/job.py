import os
import subprocess
import logging
import time
import argparse
import json
import copy
from threading import Thread, currentThread
from datetime import datetime, timezone
from pathlib import Path
import toml

import zmq
import psutil

from tomato.models import Pipeline, Reply, Daemon, Job
from tomato import tomato

logger = logging.getLogger(__name__)

def find_matching_pipelines(pipelines: dict, method: list[dict]) -> list[str]:
    req_names = set([item.device for item in method])
    req_capabs = set([item.technique for item in method])

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


def manage_running_pips(daemon: Daemon, req):
    logger = logging.getLogger(f"{__name__}.manage_running_pips")
    running = [pip for pip in daemon.pips.values() if pip.jobid is not None]
    for pip in running:
        job = daemon.jobs[pip.jobid]
        if job.pid is None:
            continue
        pidexists = psutil.pid_exists(job.pid)
        reset = False
        # running jobs scheduled for killing (status == 'rd') should be killed
        if pidexists and job.status == "rd":
            logger.debug(f"job {job.id} with pid {job.pid} will be terminated")
            proc = psutil.Process(pid=job.pid)
            kill_tomato_job(proc)
            logger.info(f"job {job.id} with pid {job.pid} was terminated successfully")
            reset = True
            params = dict(status="cd", completed_at=str(datetime.now(timezone.utc)))
        # dead jobs marked as running (status == 'r') should be cleared
        elif (not pidexists) and job.status == "r":
            logging.warning(f"the pid {job.pid} of job {job.id} has not been found")
            reset = True
            params = dict(status="ce", completed_at=str(datetime.now(timezone.utc)))
        if reset:
            req.send_pyobj(dict(cmd="job", id=job.id, params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set job {job.id} to status 'cd'")
                continue
            logger.debug(f"pipeline {pip.name} will be reset")
            params = dict(pid=None, jobid=None, ready=False)
            req.send_pyobj(dict(cmd="pipeline", pipeline=pip.name, params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set params {params} on pip: {pip.name!r}")
                continue


def check_queued_jobs(daemon: Daemon, req) -> dict[int, Pipeline]:
    logger = logging.getLogger(f"{__name__}.check_queued_jobs")
    matched = {}
    queue = [job for job in daemon.jobs.values() if job.status in {"q", "qw"}]
    for job in queue:
        matched[job.id] = find_matching_pipelines(daemon.pips, job.payload.method)
        if len(matched[job.id]) > 0 and job.status == "q":
            logger.info(
                f"job {job.id} can queue on pips: {[p.name for p in matched[job.id]]}"
            )
            req.send_pyobj(dict(cmd="job", id=job.id, params=dict(status="qw")))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set status of job {job.id}")
                continue
            else:
                job.status = "qw"
    return matched


def action_queued_jobs(daemon, matched, req):
    logger = logging.getLogger(f"{__name__}.action_queued_jobs")
    for jobid in sorted(matched.keys()):
        job = daemon.jobs[jobid]
        for pip in matched[job.id]:
            if not pip.ready:
                continue
            elif pip.sampleid != job.payload.sample.name:
                continue
            logger.info(f"job {job.id} found a matched & ready pip: {pip.name!r}")
            params = dict(jobid=job.id, ready=False)
            req.send_pyobj(dict(cmd="pipeline", pipeline=pip.name, params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set params {params} on pip: {pip.name!r}")
                continue
            else:
                pip.ready = False
            
            root = Path(daemon.settings["jobs"]["storage"]) / str(job.id)
            os.makedirs(root)
            
            jpath = root / "jobdata.json"
            jobargs = {
                "pipeline": pip.dict(),
                "payload": job.payload.dict(),
                "job": dict(id = job.id, path=str(root)),
            }
            
            with jpath.open("w", encoding="UTF-8") as of:
                json.dump(jobargs, of, indent=1)
            
            cmd = ["tomato-job", "--port", str(daemon.port), str(jpath)]
            if psutil.WINDOWS:
                cfs = subprocess.CREATE_NO_WINDOW
                cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(cmd, creationflags=cfs)
            elif psutil.POSIX:
                subprocess.Popen(cmd, start_new_session=True)
            logger.info(f"job {jobid} started on pip: {pip.name!r} and path: {jpath!r}")
            break


def manager(port: int, context: zmq.Context):
    logger = logging.getLogger(f"{__name__}.manager")
    thread = currentThread()
    logger.info(f"launched successfully")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    timeout = 1000
    while getattr(thread, "do_run"):
        req.send_pyobj(dict(cmd="status", with_data=True))
        events = dict(poller.poll(timeout))
        if req not in events:
            logger.warning(f"could not contact daemon in {timeout} ms")
            timeout = timeout * 2
            continue
        daemon = req.recv_pyobj().data
        manage_running_pips(daemon, req)
        matched_pips = check_queued_jobs(daemon, req)
        action_queued_jobs(daemon, matched_pips, req)
    logger.info(f"instructed to quit")

