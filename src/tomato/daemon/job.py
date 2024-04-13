"""
**tomato.daemon.job**: the job manager of tomato daemon
-------------------------------------------------------
.. codeauthor::
    Peter Kraus

.. note::

    Functions in this module that receive the :class:`~tomato.models.Daemon` state
    object should be acting on a copy. All changes to the :class:`Daemon` state have to
    be propagated via the :class:`tomato.daemon.cmd` set of functions.

"""

import os
import subprocess
import logging
import json
import time
import argparse
from importlib import metadata
from datetime import datetime, timezone
from pathlib import Path
from threading import currentThread
from multiprocessing import Process, Event

import zmq
import psutil

from tomato.daemon.io import merge_netcdfs, data_to_pickle
from tomato.models import Pipeline, Daemon, Component, Device, Driver

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
    """
    Wrapper around :func:`psutil.terminate`.

    Here we kill the (grand)children of the process with the name of `tomato-job`,
    i.e. the individual task functions. This allows the `tomato-job` process to exit
    gracefully once the task functions join.

    Note that on Windows, the `tomato-job.exe` process has two children: a `python.exe`
    which is the actual process running the job, and `conhost.exe`, which we want to
    avoid killing.

    """
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
        proc.terminate()
    gone, alive = psutil.wait_procs(to_kill, timeout=1)
    logger.debug(f"{gone=}")
    logger.debug(f"{alive=}")


def manage_running_pips(daemon: Daemon, req):
    """
    Function that manages jobs and `tomato-daemon` pipelines.

    The function only affects pipelines marked as running, i.e. with a set ``jobid``.
    Jobs scheduled for killing (i.e. ``status == "rd"``) are terminated. Jobs that
    are supposed to be running but have crashed are given appropriate status (``"ce"``).
    Pipelines of both are reset.

    Successful job completions are not processed here, but within the job process.

    """
    logger = logging.getLogger(f"{__name__}.manage_running_pips")
    running = [pip for pip in daemon.pips.values() if pip.jobid is not None]
    logger.debug(f"{running=}")
    for pip in running:
        job = daemon.jobs[pip.jobid]
        logger.debug(f"{job=}")
        if job.pid is None:
            continue
        pidexists = psutil.pid_exists(job.pid)
        logger.debug(f"{pidexists=}")
        reset = False
        # running jobs scheduled for killing (status == 'rd') should be killed
        if pidexists and job.status == "rd":
            logger.debug(f"job {job.id} with pid {job.pid} will be terminated")
            proc = psutil.Process(pid=job.pid)
            kill_tomato_job(proc)
            logger.info(f"job {job.id} with pid {job.pid} was terminated successfully")
            reset = True
            params = dict(status="cd")
        # dead jobs marked as running (status == 'r') should be cleared
        elif (not pidexists) and job.status == "r":
            logging.warning(f"the pid {job.pid} of job {job.id} has not been found")
            reset = True
            params = dict(status="ce")
        if reset:
            params.update(dict(completed_at=str(datetime.now(timezone.utc)), pid=None))
            req.send_pyobj(dict(cmd="job", id=job.id, params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set job {job.id} status {params['status']!r}")
                continue
            logger.debug(f"pipeline {pip.name!r} will be reset")
            params = dict(jobid=None, ready=False, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set params {params} on pip: {pip.name!r}")
                continue


def check_queued_jobs(daemon: Daemon, req) -> dict[int, list[Pipeline]]:
    """
    Function to check whether the queued jobs can be submitted onto any pipeline.

    Returns a :class:`dict` containing the jobids as keys and lists of matched
    :class:`Pipelines` as values.
    """
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
    """
    Function that assigns jobs if a matched pipeline contains the requested sample.

    The `tomato-job` process is launched from this function.
    """
    logger = logging.getLogger(f"{__name__}.action_queued_jobs")
    for jobid in sorted(matched.keys()):
        job = daemon.jobs[jobid]
        for pip in matched[job.id]:
            if not pip.ready:
                continue
            elif pip.sampleid != job.payload.sample.name:
                continue
            logger.info(f"job {job.id} found a matched & ready pip: {pip.name!r}")
            params = dict(jobid=job.id, ready=False, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
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
    """
    The job manager thread of `tomato-daemon`.

    This manager ensures the job queue is iterated over and pipelines are managed/reset.
    Note that we poll the `tomato-daemon` for status only once per iteration of the main
    loop.
    """
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
        logger.debug("tick")
        req.send_pyobj(dict(cmd="status", with_data=True, sender=f"{__name__}.manager"))
        events = dict(poller.poll(to))
        if req not in events:
            logger.warning(f"could not contact tomato-daemon in {to} ms")
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


def tomato_job() -> None:
    """
    The function called when `tomato-job` is executed.

    This function is resposible for managing all activities of a single job, including
    contacting the daemon about job pid, spawning of sub-processes to run tasks on each
    Component of the Pipeline, merging data at the end of the job, and reporting back
    to the daemon once the job is successfully finished.
    """
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
        "--timeout",
        help="Timeout [ms] for driver actions.",
        default=1000,
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
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logfile, mode="a")],
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
    events = dict(poller.poll(args.timeout))
    if req in events:
        req.recv_pyobj()
    else:
        logger.warning(f"could not contact tomato-daemon in {args.timeout/1000} s")

    output = tomato["output"]
    prefix = f"results.{jobid}" if output["prefix"] is None else output["prefix"]
    outpath = Path(output["path"])
    snappath = outpath / f"snapshot.{jobid}.nc"
    logger.debug(f"output folder is {outpath}")
    if outpath.exists():
        assert outpath.is_dir()
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(outpath)

    logger.info("handing off to 'job_main_loop'")
    logger.info("==============================")
    ret = job_main_loop(context, args.port, payload, pip, jobpath, snappath)
    logger.info("==============================")

    merge_netcdfs(jobpath, outpath / f"{prefix}.nc")

    if ret is None:
        logger.info("job finished successfully, attempting to set status to 'c'")
        params = dict(status="c", completed_at=str(datetime.now(timezone.utc)))
        req.send_pyobj(dict(cmd="job", id=jobid, params=params))
        events = dict(poller.poll(args.timeout))
        if req not in events:
            logger.warning(f"could not contact tomato-daemon in {args.timeout/1000} s")
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
    events = dict(poller.poll(args.timeout))
    if req in events:
        ret = req.recv_pyobj()
        logger.debug(f"{ret=}")
        if not ret.success:
            logger.error(f"could not reset pipeline {pip!r}")
            return 1
    else:
        logger.error(f"could not contact tomato-daemon in {args.timeout/1000} s")
        return 1
    logger.info("exiting tomato-job")


def job_process(
    tasks: list,
    component: Component,
    device: Device,
    driver: Driver,
    jobpath: Path,
):
    """
    Child process of `tomato-job`, responsible for tasks on one Component of a Pipeline.

    For each task in tasks, starts the task, then monitors the Component status and polls
    for data, and moves on to the next task as instructed in the payload.

    Stores the data for that Component as a `pickle` of a :class:`xr.Dataset`.
    """
    sender = f"{__name__}.job_process"
    logger = logging.getLogger(sender)
    logger.debug(f"in job process of {component.role!r}")

    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{driver.port}")
    logger.debug(f"job process of {component.role!r} connected to tomato-daemon")

    kwargs = dict(address=component.address, channel=component.channel)

    datapath = jobpath / f"{component.role}.pkl"
    logger.debug("distributing tasks:")
    for task in tasks:
        logger.debug(f"{task=}")
        while True:
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
            if ret.success and ret.msg == "ready":
                break

        req.send_pyobj(dict(cmd="task_start", params={**task, **kwargs}))
        ret = req.recv_pyobj()
        logger.debug(f"{ret=}")

        t0 = time.perf_counter()
        while True:
            tN = time.perf_counter()
            if tN - t0 > device.pollrate:
                req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
                ret = req.recv_pyobj()
                if ret.success:
                    data_to_pickle(ret.data, datapath, role=component.role)
                t0 += device.pollrate
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
            if ret.success and ret.msg == "ready":
                break
            time.sleep(device.pollrate / 5)
        req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
        ret = req.recv_pyobj()
        if ret.success:
            data_to_pickle(ret.data, datapath, role=component.role)


def job_main_loop(
    context: zmq.Context,
    port: int,
    payload: dict,
    pipname: str,
    jobpath: Path,
    snappath: Path,
) -> None:
    """
    The main loop function of `tomato-job`, split for better readability.
    """
    sender = f"{__name__}.job_worker"
    logger = logging.getLogger(sender)

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")

    while True:
        req.send_pyobj(dict(cmd="status", with_data=True, sender=sender))
        daemon = req.recv_pyobj().data
        if all([drv.port is not None for drv in daemon.drvs.values()]):
            break
        else:
            logger.debug("not all tomato-drivers have a port, waiting")
            time.sleep(1)

    pipeline = daemon.pips[pipname]
    logger.debug(f"{pipeline=}")

    # collate steps by role
    plan = {}
    for step in payload["method"]:
        if step["device"] not in plan:
            plan[step["device"]] = []
        task = {k: v for k, v in step.items()}
        del task["device"]
        task["task"] = task.pop("technique")
        plan[step["device"]].append(task)
    logger.debug(f"{plan=}")

    # distribute plan into threads
    processes = {}
    for role, tasks in plan.items():
        component = pipeline.devs[role]
        logger.debug(f"{component=}")
        device = daemon.devs[component.name]
        logger.debug(f"{device=}")
        driver = daemon.drvs[device.driver]
        logger.debug(f"{driver=}")
        processes[role] = Process(
            target=job_process,
            args=(tasks, component, device, driver, jobpath),
            name="job-process",
        )
        processes[role].start()

    # wait until threads join or we're killed
    snapshot = payload["tomato"].get("snapshot", None)
    t0 = time.perf_counter()
    while True:
        tN = time.perf_counter()
        if snapshot is not None and tN - t0 > snapshot["frequency"]:
            logger.debug("creating snapshot")
            merge_netcdfs(jobpath, snappath)
            t0 += snapshot["frequency"]
        joined = [proc.is_alive() is False for proc in processes.values()]
        if all(joined):
            break
        else:
            # We'd like to execute this loop exactly once every second
            time.sleep(1.0 - tN % 1)
    logger.debug(f"{[proc.exitcode for proc in processes.values()]}")
    for proc in processes.values():
        if proc.exitcode != 0:
            return proc.exitcode
