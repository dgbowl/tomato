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
from threading import current_thread, Thread
import zmq
import psutil

from tomato.daemon.io import merge_netcdfs, data_to_pickle
from tomato.daemon import jobdb
from tomato.models import Pipeline, Daemon, Component, Device, Driver, Job
from dgbowl_schemas.tomato import to_payload
from dgbowl_schemas.tomato.payload import Task

logger = logging.getLogger(__name__)


def find_matching_pipelines(
    pips: dict[str, Pipeline], cmps: dict[str, Component], method: list[Task]
) -> list[Pipeline]:
    req_tags = set([item.component_tag for item in method])
    req_capabs = set([item.technique_name for item in method])

    candidates = []
    for pip in pips.values():
        roles = set()
        capabs = set()
        for comp in pip.components:
            c = cmps[comp]
            roles.add(c.role)
            capabs.update(c.capabilities)
        if req_tags.intersection(roles) == req_tags:
            if req_capabs.intersection(capabs) == req_capabs:
                candidates.append(pip)
    return candidates


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


def manage_running_pips(pips: dict, dbpath: str, req):
    """
    Function that manages jobs and `tomato-daemon` pipelines.

    The function only affects pipelines marked as running, i.e. with a set ``jobid``.
    Jobs scheduled for killing (i.e. ``status == "rd"``) are terminated. Jobs that
    are supposed to be running but have crashed are given appropriate status (``"ce"``).
    Pipelines of both are reset.

    Successful job completions are not processed here, but within the job process.

    """
    logger = logging.getLogger(f"{__name__}.manage_running_pips")
    running = [pip for pip in pips.values() if pip.jobid is not None]
    logger.debug(f"{running=}")
    for pip in running:
        job = jobdb.get_job_id(pip.jobid, dbpath)
        if job.pid is None:
            continue
        pidexists = psutil.pid_exists(job.pid)
        if pidexists:
            pidexists = psutil.Process(job.pid).status() is not psutil.STATUS_ZOMBIE
        logger.debug(f"{pidexists=}")
        reset = False
        # running jobs scheduled for killing (status == 'rd') should be killed
        if pidexists and job.status == "rd":
            logger.debug(f"job {job.id} with pid {job.pid} will be terminated")
            proc = psutil.Process(pid=job.pid)
            kill_tomato_job(proc)
            logger.info(f"job {job.id} with pid {job.pid} was terminated successfully")
            merge_netcdfs(job)
            reset = True
            params = dict(status="cd")
        # dead jobs marked as running (status == 'r') should be cleared
        elif (not pidexists) and job.status == "r":
            logging.warning(f"the pid {job.pid} of job {job.id} has not been found")
            reset = True
            params = dict(status="ce")
        # pipelines of completed jobs should be reset
        elif (not pidexists) and job.status == "c":
            logger.debug(f"the pid {job.pid} of job {job.id} has not been found")
            ready = job.payload.settings.unlock_when_done
            params = dict(jobid=None, ready=ready, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
            ret = req.recv_pyobj()
            logger.debug(f"{ret=}")
        if reset:
            params["pid"] = None
            params["completed_at"] = str(datetime.now(timezone.utc))
            jobdb.update_job_id(job.id, params, dbpath)
            logger.debug(f"pipeline {pip.name!r} will be reset")
            params = dict(jobid=None, ready=False, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set params {params} on pip: {pip.name!r}")
                continue


def check_queued_jobs(pips: dict, cmps: dict, dbpath: str) -> dict[int, list[Pipeline]]:
    """
    Function to check whether the queued jobs can be submitted onto any pipeline.

    Returns a :class:`dict` containing the jobids as keys and lists of matched
    :class:`Pipelines` as values.
    """
    logger = logging.getLogger(f"{__name__}.check_queued_jobs")
    matched = {}
    queue = jobdb.get_jobs_where("status IN ('q', 'qw')", dbpath)
    for job in queue:
        matched[job.id] = find_matching_pipelines(pips, cmps, job.payload.method)
        if len(matched[job.id]) > 0 and job.status == "q":
            logger.info(
                "job %d can queue on pips: {%s}",
                job.id,
                [p.name for p in matched[job.id]],
            )
            params = dict(status="qw")
            job = jobdb.update_job_id(job.id, params, dbpath)
    return matched


def action_queued_jobs(daemon, matched, req):
    """
    Function that assigns jobs if a matched pipeline contains the requested sample.

    The `tomato-job` process is launched from this function.
    """
    logger = logging.getLogger(f"{__name__}.action_queued_jobs")
    for jobid in sorted(matched.keys()):
        job = jobdb.get_job_id(jobid, daemon.settings["jobs"]["dbpath"])
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
                "pipeline": pip.model_dump(),
                "payload": job.payload.model_dump(),
                "devices": {dn: dev.model_dump() for dn, dev in daemon.devs.items()},
                "job": dict(id=job.id, path=str(root)),
            }

            with jpath.open("w", encoding="UTF-8") as of:
                json.dump(jobargs, of, indent=1)

            cmd = [
                "tomato-job",
                "--port",
                str(daemon.port),
                "--verbosity",
                str(daemon.verbosity),
                "--dbpath",
                str(daemon.settings["jobs"]["dbpath"]),
                str(jpath),
            ]
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
    thread = current_thread()
    logger.info("launched successfully")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    poller = zmq.Poller()
    poller.register(req, zmq.POLLIN)
    to = timeout
    while getattr(thread, "do_run"):
        logger.debug("tick")
        req.send_pyobj(dict(cmd="status", sender=f"{__name__}.manager"))
        events = dict(poller.poll(to))
        if req not in events:
            logger.warning(f"could not contact tomato-daemon in {to} ms")
            to = to * 2
            continue
        elif to > timeout:
            to = timeout
        daemon = req.recv_pyobj().data
        dbpath = daemon.settings["jobs"]["dbpath"]
        manage_running_pips(daemon.pips, dbpath, req)
        matched_pips = check_queued_jobs(daemon.pips, daemon.cmps, dbpath)
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
        version=f"%(prog)s version {metadata.version('tomato')}",
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
        "--retries",
        help="Number of retries for driver actions.",
        default=10,
        type=int,
    )
    parser.add_argument(
        "--verbosity",
        help="Verbosity of the tomato-job.",
        default=logging.INFO,
        type=int,
    )
    parser.add_argument(
        "--dbpath",
        help="Path to the sqlite3 job database.",
        type=str,
    )
    parser.add_argument(
        "jobfile",
        type=Path,
        help="Path to a ketchup-processed payload json file.",
    )
    args = parser.parse_args()

    with args.jobfile.open() as infile:
        jsdata = json.load(infile)
    payload = to_payload(**jsdata["payload"])

    pip = jsdata["pipeline"]["name"]
    jobid = jsdata["job"]["id"]
    jobpath = Path(jsdata["job"]["path"]).resolve()

    logpath = jobpath / f"job-{jobid}.log"
    logging.basicConfig(
        level=args.verbosity,
        format="%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s",
        handlers=[logging.FileHandler(logpath, mode="a")],
    )
    logger = logging.getLogger(__name__)

    logger.debug(f"{payload=}")

    verbosity = payload.settings.verbosity
    loglevel = logging._checkLevel(verbosity)
    logger.debug("setting logger verbosity to '%s'", verbosity)
    logger.setLevel(loglevel)

    if psutil.WINDOWS:
        pid = os.getppid()
    elif psutil.POSIX:
        pid = os.getpid()

    logger.debug(f"assigning job {jobid} with pid {pid} into pipeline {pip!r}")
    context = zmq.Context()

    params = dict(pid=pid, status="r", executed_at=str(datetime.now(timezone.utc)))
    job = jobdb.update_job_id(jobid, params, args.dbpath)

    output = payload.settings.output
    outpath = Path(output.path)
    logger.debug(f"output folder is {outpath}")
    if outpath.exists():
        assert outpath.is_dir()
    else:
        logger.debug("path does not exist, creating")
        os.makedirs(outpath)
    prefix = f"results.{jobid}" if output.prefix is None else output.prefix
    respath = outpath / f"{prefix}.nc"
    snappath = outpath / f"snapshot.{jobid}.nc"
    params = dict(respath=str(respath), snappath=str(snappath), jobpath=str(jobpath))
    job = jobdb.update_job_id(jobid, params, args.dbpath)

    logger.info("handing off to 'job_main_loop'")
    logger.info("==============================")
    job_main_loop(context, args.port, job, pip, logpath)
    logger.info("==============================")

    logger.info("job finished successfully, setting job status to 'c'")
    job.completed_at = str(datetime.now(timezone.utc))
    job.status = "c"
    params = dict(status=job.status, completed_at=job.completed_at)
    job = jobdb.update_job_id(job.id, params, args.dbpath)

    logger.info("writing final data to a NetCDF file")
    merge_netcdfs(job)

    logger.debug(f"{job=}")
    logger.info("exiting tomato-job")


def job_thread(
    tasks: list,
    component: Component,
    device: Device,
    driver: Driver,
    jobpath: Path,
    logpath: Path,
):
    """
    A subthread of `tomato-job`, responsible for tasks on one Component of a Pipeline.

    For each task in tasks, starts the task, then monitors the Component status and polls
    for data, and moves on to the next task as instructed in the payload.

    Stores the data for that Component as a `pickle` of a :class:`xr.Dataset`.
    """
    sender = f"{__name__}.job_thread({current_thread().ident})"
    logger = logging.getLogger(sender)
    logger.debug(f"in job thread of {component.role!r}")

    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{driver.port}")
    logger.debug(f"job thread of {component.role!r} connected to tomato-daemon")

    kwargs = dict(address=component.address, channel=component.channel)

    datapath = Path(jobpath) / f"{component.role}.pkl"
    logger.debug("distributing tasks:")
    for task in tasks:
        logger.debug(f"{task=}")
        while True:
            logger.debug("polling component '%s' for task readiness", component.role)
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            if ret.success and ret.data["can_submit"]:
                break
            logger.warning("cannot submit onto component '%s', waiting", component.role)
            time.sleep(1e-1)
        logger.debug("sending task to component '%s'", component.role)
        req.send_pyobj(dict(cmd="task_start", params={"task": task, **kwargs}))
        ret = req.recv_pyobj()

        t0 = time.perf_counter()
        while True:
            tN = time.perf_counter()
            if tN - t0 > device.pollrate:
                logger.debug("polling component '%s' for data", component.role)
                req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
                ret = req.recv_pyobj()
                if ret.success:
                    logger.debug("pickling received data")
                    ds = ret.data
                    ds.attrs["tomato_Component"] = component.model_dump_json()
                    data_to_pickle(ds, datapath, role=component.role)
                t0 += device.pollrate

            logger.debug("polling component '%s' for task completion", component.role)
            req.send_pyobj(dict(cmd="task_status", params={**kwargs}))
            ret = req.recv_pyobj()
            if ret.success and not ret.data["running"]:
                logger.debug("task no longer running, break")
                break
            time.sleep(max(1e-1, (device.pollrate - (tN - t0)) / 2))

        logger.debug("fetching final data for task")
        req.send_pyobj(dict(cmd="task_data", params={**kwargs}))
        ret = req.recv_pyobj()
        if ret.success:
            data_to_pickle(ret.data, datapath, role=component.role)
    logger.debug("all tasks done on component '%s', resetting", component.role)
    req.send_pyobj(dict(cmd="dev_reset", params={**kwargs}))
    ret = req.recv_pyobj()
    if not ret.success:
        logger.warning("could not reset component '%s': %s", component.role, ret.msg)


def job_main_loop(
    context: zmq.Context,
    port: int,
    job: Job,
    pipname: str,
    logpath: Path,
) -> None:
    """
    The main loop function of `tomato-job`, split for better readability.
    """
    sender = f"{__name__}.job_main_loop"
    logger = logging.getLogger(sender)
    logger.debug("process started")

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")

    while True:
        req.send_pyobj(dict(cmd="status", sender=sender))
        daemon: Daemon = req.recv_pyobj().data
        if all([drv.port is not None for drv in daemon.drvs.values()]):
            break
        else:
            logger.debug("not all tomato-drivers have a port, waiting")
            time.sleep(1)

    pipeline = daemon.pips[pipname]
    logger.debug(f"{pipeline=}")
    logger.debug(f"{job=}")

    # collate steps by role
    plan = {}
    for step in job.payload.method:
        if step.component_tag not in plan:
            plan[step.component_tag] = []
        plan[step.component_tag].append(step)
    logger.debug(f"{plan=}")

    # distribute plan into threads
    threads = {}
    for cmpk in pipeline.components:
        component = daemon.cmps[cmpk]
        logger.debug(f"{component=}")
        if component.role not in plan:
            continue
        tasks = plan[component.role]
        logger.debug(" tasks=%s", tasks)
        device = daemon.devs[component.device]
        logger.debug(" device=%s", device)
        driver = daemon.drvs[component.driver]
        logger.debug(" driver=%s", driver)
        threads[component.role] = Thread(
            target=job_thread,
            args=(tasks, component, device, driver, job.jobpath, logpath),
            name="job-thread",
        )
        threads[component.role].start()

    # wait until threads join or we're killed
    snapshot = job.payload.settings.snapshot
    t0 = time.perf_counter()
    while True:
        logger.debug("tick")
        tN = time.perf_counter()
        if snapshot is not None and tN - t0 > snapshot.frequency:
            logger.debug("creating snapshot")
            merge_netcdfs(job, snapshot=True)
            t0 += snapshot.frequency
        joined = [proc.is_alive() is False for proc in threads.values()]
        if all(joined):
            break
        else:
            # We'd like to execute this loop exactly once every second
            time.sleep(1.0 - tN % 1)
