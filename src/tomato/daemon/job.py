import os
import subprocess
import logging
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import currentThread

import signal
import zmq
import psutil

from tomato.models import Pipeline, Daemon

logger = logging.getLogger(__name__)


def find_matching_pipelines(daemon: Daemon, method: list[dict]) -> list[str]:
    req_names = set([item.device for item in method])
    req_capabs = set([item.technique for item in method])

    candidates = []
    for pip in daemon.pips.values():
        dnames = set([comp.role for comp in pip.devs.values()])
        if req_names.intersection(dnames) == req_names:
            candidates.append(pip)

    matched = []
    for cd in candidates:
        capabs = []
        for dev in cd.devs.values():
            capabs += daemon.devs[dev.name].capabilities
        if req_capabs.intersection(set(capabs)) == req_capabs:
            matched.append(cd)
    return matched


def kill_tomato_job(process: psutil.Process):
    logger = logging.getLogger(f"{__name__}.kill_tomato_job")
    if psutil.WINDOWS:
        pc = [p for p in process.children() if p.name() not in {"conhost.exe"}]
        to_kill = []
        for child in pc:
            to_kill += child.children()
    elif psutil.POSIX:
        to_kill = [p for p in process.children()]
    for proc in to_kill:
        logger.warning(f"killing process {proc.name()!r} with pid {proc.pid}")
        # os.kill(proc.pid, sig)
        proc.terminate()
    gone, alive = psutil.wait_procs(to_kill, timeout=1)
    logger.debug(f"{gone=}")
    logger.debug(f"{alive=}")


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
            params = dict(jobid=None, ready=False)
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
        matched[job.id] = find_matching_pipelines(daemon, job.payload.method)
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
                "devices": {dname: dev.dict() for dname, dev in daemon.devs.items()},
                "job": dict(id=job.id, path=str(root)),
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


def manager(port: int, timeout: int = 500):
    context = zmq.Context()
    logger = logging.getLogger(f"{__name__}.manager")
    thread = currentThread()
    logger.info("launched successfully")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    to = timeout
    while getattr(thread, "do_run"):
        req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
        events = dict(poller.poll(to))
        if req not in events:
            logger.warning(f"could not contact daemon in {to} ms")
            to = to * 2
            continue
        elif to > timeout:
            to = timeout
        daemon = req.recv_pyobj().data
        manage_running_pips(daemon, req)
        matched_pips = check_queued_jobs(daemon, req)
        action_queued_jobs(daemon, matched_pips, req)
        time.sleep(timeout / 1e3)
    logger.info("instructed to quit")
