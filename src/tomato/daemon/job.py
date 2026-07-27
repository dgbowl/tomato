"""
**tomato.daemon.job**: the job manager of tomato daemon
-------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from threading import Thread, current_thread
from typing import Sequence

import psutil
import xarray as xr
import zmq

from tomato.daemon import drvdb, jobdb, lpp, pipdb
from tomato.daemon.crates import to_rocrate
from tomato.daemon.io import data_to_pickle, merge_netcdfs
from tomato.models import (
    Component,
    Daemon,
    Device,
    Job,
    Pipeline,
    Task,
    to_payload,
)
from tomato.utils import context

logger = logging.getLogger(__name__)

MAX_JOB_NOPID = timedelta(seconds=10)
MAX_TASK_WAIT = 10
JOB_INFO_INTERVAL = 5


def method_validate(
    method: Sequence[Task],
    pip: Pipeline,
    daemon: Daemon,
) -> bool:
    """
    Function for validating :class:`Task` parameters against components.

    This function finds a component on the pipeline that matches the role of each :class:`Task`, and passes each :class:`Task` to the :func:`task_validate` function of that component.

    .. note::

        This function should be used to theck the method only after a matching pipeline has been identified, e.g. using :func:`find_matching_pipelines`.

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    for task in method:
        for crole, cname in pip.components.items():
            if task.component_role == crole:
                cmp = daemon.devicefile.components[cname]
                drv = drvdb.get_drv(name=cmp.driver, dbpath=dbpath)
                assert drv is not None
                req: zmq.Socket = context.socket(zmq.REQ)
                req.connect(f"tcp://127.0.0.1:{drv.port}")
                params = dict(task=task, address=cmp.address, channel=cmp.channel)
                ret, req = lpp.comm(
                    req,
                    dict(cmd="task_validate", params=params),
                    f"tcp://127.0.0.1:{drv.port}",
                )
                if ret.success:
                    req.close()
                    break
        else:
            return False
    return True


def find_matching_pipelines(
    daemon: Daemon,
    method: Sequence[Task],
) -> list[str]:
    """
    Function for finding the names of pipelines that match the provided method.

    The matching is performed using the required roles of the method as well as using the required capabilities of the method. The role-matching can be checked statically against the :obj:`daemon.devicefile`; the latter is checked dynamically by polling each component for its capabilities using :func:`cmp_capabilities`.
    """
    req_roles = set([item.component_role for item in method])
    req_capabs = set([item.technique_name for item in method])
    dbpath = daemon.settings["jobs"]["dbpath"]

    candidates = []
    for pip in daemon.devicefile.pipelines.values():
        roles = set(pip.components.keys())
        if req_roles.intersection(roles) != req_roles:
            continue
        capabs = set()
        for cname in pip.components.values():
            cmp = daemon.devicefile.components[cname]
            drv = drvdb.get_drv(name=cmp.driver, dbpath=dbpath)
            assert drv is not None
            dreq = context.socket(zmq.REQ)
            dreq.connect(f"tcp://127.0.0.1:{drv.port}")
            params = dict(address=cmp.address, channel=cmp.channel)
            dreq.send_pyobj(dict(cmd="cmp_capabilities", params=params))
            dret = dreq.recv_pyobj()
            if dret.success and dret.data is not None:
                capabs.update(dret.data)
        if req_capabs.intersection(capabs) == req_capabs:
            if method_validate(method, pip, daemon):
                candidates.append(pip.name)
    return candidates


def kill_tomato_job(process: psutil.Process):
    """
    Wrapper around :func:`psutil.terminate`.

    Here we kill the (grand)children of the process with the name of `tomato-job`, i.e. the individual task functions. This allows the `tomato-job` process to exit gracefully once the task functions join.

    .. note::

        On Windows, the `tomato-job.exe` process has two children: a `python.exe` process, which is the actual process running the job, and `conhost.exe` process, which we want to avoid killing.

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


def manage_running(daemon: Daemon):
    """
    Function that manages jobs within the tomato job manager.

    The function only affects jobs marked as running, i.e. with a set ``pid``. Jobs scheduled for killing (i.e. ``status == "rd"``) are terminated. Jobs that are supposed to be running but have crashed are given appropriate status (``"ce"``).

    .. note ::

        Successful job completions are not processed here, but within the job process.

    """
    logger = logging.getLogger(f"{__name__}.manage_running")
    dbpath = daemon.settings["jobs"]["dbpath"]
    running: list[Job] = jobdb.get_jobs_where("pid IS NOT NULL", dbpath)
    for job in running:
        logger.debug("%d: checking job status", job.id)
        if job.pid is None and job.connected_at is not None:
            # pid is set in the same command as connected_at
            # unclear how we'd end here
            logger.error("%d: job status shouldn't be possible: %s", job.id, job)
            pidexists = False
        elif job.pid is None and job.launched_at is not None:
            # subprocess was started but job is not (yet) connected
            td = datetime.now(timezone.utc) - datetime.fromisoformat(job.launched_at)
            if td > MAX_JOB_NOPID:
                logger.error("job %d failed to register, aborting", job.id)
                job.status = "rd"
                pidexists = False
            else:
                continue
        elif job.pid is None:
            # subprocess was not yet started
            logger.warning("%d: job failed to start", job.id)
            # TODO: timeout to be implemented
            continue
        else:
            pidexists = psutil.pid_exists(job.pid)
        if pidexists:
            pidexists = psutil.Process(job.pid).status() is not psutil.STATUS_ZOMBIE

        # running jobs scheduled for killing (status == 'rd') should be killed
        # jobs that have status == 'rd' but no valid pid should be cleared
        if job.status == "rd":
            if pidexists:
                logger.info("%d: job with pid %d will be terminated", job.id, job.pid)
                proc = psutil.Process(pid=job.pid)
                kill_tomato_job(proc)
                merge_netcdfs(job)
                logger.info("%d: job with pid %d was terminated", job.id, job.pid)
            update = True
            params = dict(status="cd", pid=None)
        # dead jobs marked as running (status == 'r') should be cleared
        elif (not pidexists) and job.status == "r":
            logger.warning("%d: the pid %d of the job was not found", job.id, job.pid)
            update = True
            params = dict(status="ce", pid=None)
        else:
            update = False

        if update:
            logger.debug(f"job {job.id} will be updated to status {params['status']!r}")
            params["completed_at"] = str(datetime.now(timezone.utc))
            jobdb.update_job_id(job.id, params, dbpath)


def check_queued(daemon: Daemon) -> dict[int, list[str]]:
    """
    Function to check whether the queued jobs can be submitted onto any configured pipeline.

    Returns a :class:`dict` containing the jobids as keys and lists of matched :class:`Pipelines` as values.
    """
    logger = logging.getLogger(f"{__name__}.check_queued")
    matched = {}
    dbpath = daemon.settings["jobs"]["dbpath"]
    queue = jobdb.get_jobs_where("status IN ('q', 'qw')", dbpath)
    for job in queue:
        matched[job.id] = find_matching_pipelines(daemon, job.payload.method)
        if len(matched[job.id]) > 0 and job.status == "q":
            logger.info(
                "job %d can queue on pips: {%s}",
                job.id,
                matched[job.id],
            )
            params = dict(status="qw")
            jobdb.update_job_id(job.id, params, dbpath)
    return matched


def action_queued(
    daemon: Daemon,
    matched: dict[int, list[str]],
):
    """
    Function that assigns jobs if the pipeline is ready and contains the requested sample.

    .. warning::

        No validation except checking the sample name and readiness is performed. A matching and validated pipeline has to be previously identified, using e.g. the :func:`check_queued` function.

    .. note::

        The `tomato-job` process is launched from this function.

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    logger = logging.getLogger(f"{__name__}.action_queued")
    # We have to cache the available pipelines once per queue pass
    # in order to avoid race conditions, where the pipeline in the
    # sqlite database is made available in the middle of the loop
    # over the jobs.
    where = "jobid IS NULL"
    avail_pips = {p.name: p for p in pipdb.get_pips_where(where=where, dbpath=dbpath)}
    for jobid in sorted(matched.keys()):
        job = jobdb.get_job_id(jobid, daemon.settings["jobs"]["dbpath"])
        for pname in matched[jobid]:
            ps = avail_pips.get(pname)
            if ps is None:
                # This happens if the pipeline has already been popped below
                continue
            elif not ps.ready:
                continue
            elif ps.sampleid != job.payload.sample.identifier:
                continue
            logger.info("job %d: found a matched & ready pip '%s'", jobid, pname)

            logger.debug("job %d: making job directory", jobid)
            root = Path(daemon.settings["jobs"]["storage"]) / str(jobid)
            os.makedirs(root)

            logger.debug("job %d: storing jobdata.json", jobid)
            jpath = root / "jobdata.json"
            repositories = {}
            for repo, repoparams in daemon.settings["repositories"].items():
                if repo in job.payload.settings.output.repositories:
                    repositories[repo] = repoparams
            jobargs = {
                "pipeline": daemon.devicefile.pipelines[pname].model_dump(),
                "payload": job.payload.model_dump(),
                "repositories": repositories,
                "job": dict(id=job.id, path=str(root)),
            }
            with jpath.open("w", encoding="UTF-8") as of:
                json.dump(jobargs, of, indent=1)

            logger.debug("job %d: reserving pipeline %s", job.id, pname)
            params = dict(jobid=job.id, ready=False)
            pipdb.update_pip(name=pname, params=params, dbpath=dbpath)
            # pop this pipeline to make sure we don't double submit
            avail_pips.pop(pname)

            logger.debug("job %d: executing tomato-job", job.id)
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

            logger.debug("job %d: setting launched_at", job.id)
            params = dict(launched_at=str(datetime.now(timezone.utc)))
            job = jobdb.update_job_id(jobid, params, dbpath)
            logger.info(
                "job %d: launched on pip '%s' and path '%s'", job.id, pname, jpath
            )
            break


def manager(timeout: int = 500):
    """
    The job manager thread of `tomato-daemon`.

    This manager ensures the job queue is iterated over and jobs are submitted to pipelines.

    .. note::

        Note that we poll the `tomato-daemon` for configuration only once per iteration of the main loop.

    """
    logger = logging.getLogger(f"{__name__}.manager")
    thread = current_thread()
    logger.info("launched successfully")
    req: zmq.Socket = context.socket(zmq.REQ)
    req.connect("inproc://daemon")
    while getattr(thread, "do_run"):
        msg = dict(cmd="status", sender=f"{__name__}.manager")
        req.send_pyobj(msg)
        ret = req.recv_pyobj()
        if req.closed:
            break
        elif ret.success is False or ret.data is None:
            logger.critical("tomato-daemon is not running: %s", ret.msg)
            break
        daemon: Daemon = ret.data
        manage_running(daemon)
        matched_pips = check_queued(daemon)
        action_queued(daemon, matched_pips)
        time.sleep(timeout / 1e3)
    req.close()
    logger.info("instructed to quit")


def tomato_job() -> None:
    """
    The function called when `tomato-job` is executed.

    This function is responsible for managing all activities of a single job, including updating the queue table with the job pid, spawning of sub-processes to run tasks on each component of the pipeline, merging data at the end of the job, and updating the state of the pipeline once the job is successfully finished.

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
    repositories = jsdata["repositories"]

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
    logger.debug(f"{jsdata=}")
    logger.debug(f"{payload=}")

    verbosity = payload.settings.verbosity
    logger.debug("setting logger verbosity to '%s'", verbosity)
    logger.setLevel(verbosity)

    if psutil.WINDOWS:
        pid = os.getpid()
        thispid = os.getpid()
        thisproc = psutil.Process(thispid)
        for p in thisproc.parents():
            if p.name() == "tomato-job.exe":
                pid = p.pid
                break
    elif psutil.POSIX:
        pid = os.getpid()

    logger.info(f"assigning job {jobid} with pid {pid} into pipeline {pip!r}")

    params = dict(pid=pid, status="r", connected_at=str(datetime.now(timezone.utc)))
    job = jobdb.update_job_id(jobid, params, args.dbpath)

    output = payload.settings.output
    outpath = Path(output.path)
    logger.info(f"output folder is {outpath}")
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
    ret = job_main_loop(args.port, job, pip, logpath)
    logger.info("==============================")

    job.completed_at = str(datetime.now(timezone.utc))

    if ret is None:
        job.status = "c"
    else:
        job.status = "ce"
    logger.info("writing final data to a NetCDF file")
    outpath = merge_netcdfs(job)
    if len(jsdata["repositories"]) > 0:
        logger.debug(
            "job configured with repositories: '%s'", list(repositories.keys())
        )
        logger.info("writing final RO-crate")
        to_rocrate(
            datapath=outpath,
            userid=job.payload.user.identifier,
            sampleid=job.payload.sample.identifier,
            make_child=job.payload.sample.sample_is_parent,
        )
    logger.info("job finished with status '%s', updating job db", job.status)
    params = dict(status=job.status, completed_at=job.completed_at)
    job = jobdb.update_job_id(job.id, params, args.dbpath)
    logger.debug(f"{job=}")
    params = dict(jobid=None, ready=job.payload.settings.unlock_when_done)
    pip = pipdb.update_pip(name=pip, params=params, dbpath=args.dbpath)
    logger.debug(f"{pip=}")
    logger.info("exiting tomato-job")


def job_thread(
    role: str,
    tasks: list[Task],
    component: Component,
    device: Device,
    dport: int,
    dsettings: dict,
    jobpath: Path,
    logpath: Path,
):
    """
    A subthread of `tomato-job`, responsible for tasks on one component of a pipeline.

    For each :class:`Task`, this thread starts the task at an appropriate moment, then monitors the component status and polls periodically for data, and moves on to the next task as instructed in the task list.

    .. note::

        The data from all tasks for that component is stored using the :func:`tomato.daemon.io.data_to_pickle` function.

    """
    thread = current_thread()
    sender = f"{__name__}.job_thread({thread.ident:5d})"
    logger = logging.getLogger(sender)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{dport}")
    lppargs = dict(endpoint=f"tcp://127.0.0.1:{dport}", sender=sender)

    if "lpp_timeout" in dsettings:
        lppargs["timeout"] = dsettings["lpp_timeout"] * 1000
        logger.debug("%s: setting lpp_timeout to %d ms", role, lppargs["timeout"])

    logger.info("%s: job thread of %s attached to tomato-daemon", role, component.name)
    kwargs = dict(address=component.address, channel=component.channel)

    datapath = Path(jobpath) / f"{role}.pkl"
    logger.debug("%s: processing tasks on component %s", role, component.name)
    for ti, task in enumerate(tasks):
        taskid = f"{role}:{ti}"
        if task.task_name is not None:
            taskid += f":{task.task_name!r}"
        setattr(thread, "current_task", task)
        logger.info("%s: processing task", taskid)

        # Hold while start contidions are not met
        while True:
            if task.start_with_task_name is None:
                break
            elif task.start_with_task_name in getattr(thread, "started_task_names"):
                break
            else:
                logger.debug(
                    "%s: waiting for task_name '%s'", taskid, task.start_with_task_name
                )
                time.sleep(0.1)

        # Hold while component task_list is not ready
        while True:
            logger.debug(
                "%s: polling component %s for task readiness", taskid, component.name
            )
            msg = dict(cmd="task_status", params={**kwargs})
            ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
            if ret.success and ret.data is not None and ret.data["can_submit"]:
                break
            elif req.closed:
                setattr(thread, "crashed", True)
                sys.exit()
            logger.warning(
                "%s: cannot submit onto component %s, waiting", taskid, component.name
            )
            time.sleep(0.1)

        # Send task to component
        logger.info("%s: sending task to component %s", taskid, component.name)
        t0 = time.perf_counter()
        msg = dict(cmd="task_start", params={"task": task, **kwargs})
        ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
        if req.closed:
            setattr(thread, "crashed", True)
            sys.exit()

        # Wait until the correct task is running, or MAX_TASK_WAIT
        while True:
            dt = time.perf_counter() - t0
            msg = dict(cmd="task_status", params={**kwargs})
            ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
            if req.closed:
                setattr(thread, "crashed", True)
                sys.exit()
            elif ret.success and ret.data is not None and ret.data["running"] is False:
                logger.warning(
                    "%s: task was submitted %f s ago but is not yet running", taskid, dt
                )
                pass
            elif (
                ret.success
                and ret.data is not None
                and "task" in ret.data
                and ret.data["task"] != task
            ):
                logger.warning(
                    "%s: task was submitted %f s ago but another task is running: %s",
                    taskid,
                    dt,
                    ret.data["task"],
                )
                pass
            elif (
                ret.success
                and ret.data is not None
                and "task" in ret.data
                and ret.data["task"] == task
            ):
                break
            elif ret.success and ret.data is not None and "task" not in ret.data:
                break
            if dt > MAX_TASK_WAIT:
                logger.critical(
                    "%s: task was submitted, but is not executed, aborting", taskid
                )
                setattr(thread, "crashed", True)
                sys.exit()
            time.sleep(0.1)
        logger.info("%s: correct task running on component %s", taskid, role)

        # Main task loop
        tP = time.perf_counter()
        while True:
            tN = time.perf_counter()

            # Poll for data every device.pollrate, save to pickle
            if tN - tP > device.pollrate:
                logger.debug("%s: polling task for data", taskid)
                msg = dict(cmd="task_data", params={**kwargs})
                ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
                if req.closed:
                    setattr(thread, "crashed", True)
                    sys.exit()
                elif ret.success and ret.data is not None:
                    logger.debug("%s: pickling received data", taskid)
                    ds: xr.Dataset = ret.data
                    ds.attrs["tomato_Component"] = component.model_dump_json()
                    data_to_pickle(ds, datapath, role=role)
                tP += device.pollrate

            # Poll for completion and correct task status
            logger.debug("%s: polling task for completion", taskid)
            msg = dict(cmd="task_status", params={**kwargs})
            ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
            if req.closed:
                setattr(thread, "crashed", True)
                sys.exit()
            elif ret.success and ret.data is not None and not ret.data["running"]:
                logger.info("%s: task no longer running, break", taskid)
                break
            elif (
                ret.success
                and ret.data is not None
                and "task" in ret.data
                and ret.data["task"] != task
            ):
                logger.critical("%s: wront task running, break", taskid)
                logger.debug("%s: expected task: %s", taskid, task)
                logger.debug("%s: executed task: %s", taskid, ret.data["task"])
                break
            elif ret.success is False:
                logger.critical(f"{ret=}")
                break

            # Stop task if stop trigger condition met, save to pickle
            if (
                task.stop_with_task_name is not None
                and task.stop_with_task_name in getattr(thread, "started_task_names")
            ):
                logger.info("%s: task stop trigger met", taskid)
                msg = dict(cmd="task_stop", params={**kwargs})
                ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
                if req.closed:
                    setattr(thread, "crashed", True)
                    sys.exit()
                elif ret.success and ret.data is not None:
                    logger.debug("%s: pickling received data", taskid)
                    ds: xr.Dataset = ret.data
                    ds.attrs["tomato_Component"] = component.model_dump_json()
                    data_to_pickle(ds, datapath, role=role)
                break

            time.sleep(max(1e-1, (device.pollrate - (tN - tP)) / 2))

        # Store final task data, housekeeping.
        logger.info("%s: task fetching final data", taskid)
        msg = dict(cmd="task_data", params={**kwargs})
        ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
        if req.closed:
            setattr(thread, "crashed", True)
            sys.exit()
        elif ret.success and ret.data is not None:
            logger.debug("%s: pickling received data", taskid)
            ds: xr.Dataset = ret.data
            ds.attrs["tomato_Component"] = component.model_dump_json()
            data_to_pickle(ds, datapath, role=role)
        ct = getattr(thread, "completed_tasks").append(task)
        setattr(thread, "completed_tasks", ct)
        setattr(thread, "current_task", None)

    # Reset component at the end of the job
    logger.info("%s: all tasks done on component %s, resetting", role, component.name)
    msg = dict(cmd="cmp_reset", params={**kwargs})
    ret, req = lpp.comm(req, msg, **lppargs)  # ty: ignore[invalid-argument-type]
    if req.closed:
        setattr(thread, "crashed", True)
        sys.exit()
    elif not ret.success:
        logger.warning("%s: could not reset component %s", role, ret.msg)
    else:
        logger.info("%s: reset of component %s done", role, component.name)
    req.close()


def job_main_loop(
    port: int,
    job: Job,
    pipname: str,
    logpath: Path,
) -> int | None:
    """
    The main loop function of `tomato-job`, split for better readability.
    """
    sender = f"{__name__}.job_main_loop"
    logger = logging.getLogger(sender)
    logger.debug("process started")

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    lppargs = dict(endpoint=f"tcp://127.0.0.1:{port}")

    while True:
        ret, req = lpp.comm(req, dict(cmd="status", sender=sender), **lppargs)  # ty: ignore[invalid-argument-type]
        if ret.success and ret.data is not None:
            daemon: Daemon = ret.data
            dbpath = daemon.settings["jobs"]["dbpath"]
        else:
            sys.exit()
        drivers = drvdb.get_drvs_where(where="name IS NOT NULL", dbpath=dbpath)
        if all([drv.port is not None for drv in drivers]):
            break
        else:
            logger.debug("not all tomato-drivers have a port, waiting")
            time.sleep(1)
    req.close()

    # pipeline = daemon.pips[pipname]
    pipeline = daemon.devicefile.pipelines[pipname]
    logger.debug(f"{pipeline=}")
    logger.debug(f"{job=}")

    # collate steps by role
    plan = {}
    for step in job.payload.method:
        if step.component_role not in plan:
            plan[step.component_role] = []
        plan[step.component_role].append(step)
    logger.debug(f"{plan=}")

    # distribute plan into threads
    threads = {}
    for crole, cname in pipeline.components.items():
        cmp = daemon.devicefile.components[cname]
        logger.debug(f"{cmp=}")
        if crole not in plan:
            continue
        tasks = plan[crole]
        logger.debug(" tasks=%s", tasks)
        device = daemon.devicefile.devices[cmp.device]
        logger.debug(" device=%s", device)
        drv = drvdb.get_drv(name=cmp.driver, dbpath=dbpath)
        assert drv is not None
        dsettings = daemon.devicefile.drivers[cmp.driver].settings
        logger.debug(" settings=%s", dsettings)
        threads[crole] = Thread(
            target=job_thread,
            args=(crole, tasks, cmp, device, drv.port, dsettings, job.jobpath, logpath),
            name="job-thread",
            daemon=False,
        )
        setattr(threads[crole], "crashed", False)
        setattr(threads[crole], "completed_tasks", [])
        setattr(threads[crole], "current_task", None)
        setattr(threads[crole], "started_task_names", set())
        threads[crole].start()

    # wait until threads join or we're killed
    snapshot = job.payload.settings.snapshot
    tS = time.perf_counter()
    tD = tS
    started_task_names = set()
    logger.debug("polling threads until completion")
    while True:
        tN = time.perf_counter()
        if snapshot is not None and tN - tS > snapshot.interval:
            logger.debug("creating snapshot")
            merge_netcdfs(job, snapshot=True)
            tS += snapshot.interval

        # Collect and push task names
        for t in threads.values():
            current_task = getattr(t, "current_task")
            if current_task is not None and current_task.task_name is not None:
                started_task_names.add(current_task.task_name)
        for t in threads.values():
            stn = getattr(t, "started_task_names")
            stn.update(started_task_names)
            setattr(t, "started_task_names", stn)
        crashed = [getattr(t, "crashed") for t in threads.values()]
        joined = [
            t.is_alive() is False or getattr(t, "crashed") for t in threads.values()
        ]
        if tN - tD > JOB_INFO_INTERVAL:
            logger.info("started task names are: %s", started_task_names)
            logger.info("joined threads are: %s", joined)
            logger.info("crashed threads are: %s", crashed)
            tD += JOB_INFO_INTERVAL
        if all(joined):
            break
        # We'd like to execute this loop exactly once every second
        time.sleep(1.0 - tN % 1)

    logger.info("all threads have joined")
    if any(crashed):
        return 1
    else:
        return None
