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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import current_thread, Thread
import zmq
import psutil
import sys
import xarray as xr

from tomato.daemon.io import merge_netcdfs, data_to_pickle
from tomato.daemon import jobdb, lpp
from tomato.models import Pipeline, Daemon, Component, Device, Driver, Job
from dgbowl_schemas.tomato import to_payload
from dgbowl_schemas.tomato.payload import Task

logger = logging.getLogger(__name__)

MAX_JOB_NOPID = timedelta(seconds=10)


def method_validate(
    method: list[Task],
    pip: Pipeline,
    drvs: dict[str, Driver],
    cmps: dict[str, Component],
    context: zmq.Context,
):
    for task in method:
        for cmp in pip.components:
            if task.technique_name in cmps[cmp].capabilities:
                drv = drvs[cmps[cmp].driver]
                if drv.version == "1.0":
                    logger.info("cannot validate task using DriverInterface-1.0")
                    break
                req: zmq.Socket = context.socket(zmq.REQ)
                req.connect(f"tcp://127.0.0.1:{drv.port}")
                params = dict(
                    task=task,
                    address=cmps[cmp].address,
                    channel=cmps[cmp].channel,
                )
                ret, req = lpp.comm(
                    req,
                    dict(cmd="task_validate", params=params),
                    f"tcp://127.0.0.1:{drv.port}",
                    context,
                )
                if ret.success:
                    req.close()
                    break
        else:
            return False
    return True


def find_matching_pipelines(
    pips: dict[str, Pipeline],
    cmps: dict[str, Component],
    drvs: dict[str, Driver],
    method: list[Task],
    context: zmq.Context,
) -> list[Pipeline]:
    req_roles = set([item.component_role for item in method])
    req_capabs = set([item.technique_name for item in method])

    candidates = []
    for pip in pips.values():
        roles = set()
        capabs = set()
        for comp in pip.components:
            c = cmps[comp]
            if c.capabilities is not None:
                roles.add(c.role)
                capabs.update(c.capabilities)
        if req_roles.intersection(roles) == req_roles:
            if req_capabs.intersection(capabs) == req_capabs:
                if method_validate(method, pip, drvs, cmps, context):
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


def manage_running_pips(pips: dict, dbpath: str, req: zmq.Socket):
    """
    Function that manages jobs and `tomato-daemon` pipelines.

    The function only affects pipelines marked as running, i.e. with a set ``jobid``.
    Jobs scheduled for killing (i.e. ``status == "rd"``) are terminated. Jobs that
    are supposed to be running but have crashed are given appropriate status (``"ce"``).
    Pipelines of both are reset.

    Successful job completions are not processed here, but within the job process.

    """
    logger = logging.getLogger(f"{__name__}.manage_running_pips")
    running: list[Pipeline] = [pip for pip in pips.values() if pip.jobid is not None]
    logger.debug(f"{running=}")
    for pip in running:
        job = jobdb.get_job_id(pip.jobid, dbpath)

        if job.pid is None and job.connected_at is not None:
            # pid is set in the same command as connected_at
            # unclear how we'd end here
            logger.error("job status shouldn't be possible: %s", job)
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
            logger.warning("job %d failed to start", job.id)
            # TODO: timeout to be implemented
            continue
        else:
            pidexists = psutil.pid_exists(job.pid)
        if pidexists:
            pidexists = psutil.Process(job.pid).status() is not psutil.STATUS_ZOMBIE

        reset = False
        update = False
        ready = False
        # running jobs scheduled for killing (status == 'rd') should be killed
        # jobs that have status == 'rd' but no valid pid should be cleared
        if job.status == "rd":
            if pidexists:
                logger.info(f"job {job.id} with pid {job.pid} will be terminated")
                proc = psutil.Process(pid=job.pid)
                kill_tomato_job(proc)
                logger.info(
                    f"job {job.id} with pid {job.pid} was terminated successfully"
                )
                merge_netcdfs(job)
            update = True
            params = dict(status="cd")
            reset = True
        # dead jobs marked as running (status == 'r') should be cleared
        elif (not pidexists) and job.status == "r":
            logger.warning(f"the pid {job.pid} of running job {job.id} was not found")
            reset = True
            update = True
            params = dict(status="ce")
        # crashed jobs marked as such (status == 'ce') should also be cleared
        elif (not pidexists) and job.status in {"ce", "cd"}:
            logger.info(f"the pid {job.pid} of crashed job {job.id} was not found")
            reset = True
        # pipelines of completed jobs should be reset
        elif (not pidexists) and job.status == "c":
            logger.info(f"the pid {job.pid} of completed job {job.id} was not found")
            ready = job.payload.settings.unlock_when_done
            reset = True

        if update:
            logger.debug(f"job {job.id} will be updated to status {params['status']!r}")
            params["pid"] = None
            params["completed_at"] = str(datetime.now(timezone.utc))
            jobdb.update_job_id(job.id, params, dbpath)
        if reset:
            logger.debug(f"pipeline {pip.name!r} will be reset")
            params = dict(jobid=None, ready=ready, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error(f"could not set params {params} on pip: {pip.name!r}")
                continue


def check_queued_jobs(
    pips: dict,
    cmps: dict,
    drvs: dict,
    dbpath: str,
    context: zmq.Context,
) -> dict[int, list[Pipeline]]:
    """
    Function to check whether the queued jobs can be submitted onto any pipeline.

    Returns a :class:`dict` containing the jobids as keys and lists of matched
    :class:`Pipelines` as values.
    """
    logger = logging.getLogger(f"{__name__}.check_queued_jobs")
    matched = {}
    queue = jobdb.get_jobs_where("status IN ('q', 'qw')", dbpath)
    for job in queue:
        matched[job.id] = find_matching_pipelines(
            pips, cmps, drvs, job.payload.method, context
        )
        if len(matched[job.id]) > 0 and job.status == "q":
            logger.info(
                "job %d can queue on pips: {%s}",
                job.id,
                [p.name for p in matched[job.id]],
            )
            params = dict(status="qw")
            job = jobdb.update_job_id(job.id, params, dbpath)
    return matched


def action_queued_jobs(daemon, matched, req, dbpath):
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
            logger.info("job %d: found a matched & ready pip '%s'", job.id, pip.name)

            logger.debug("job %d: making job directory", job.id)
            root = Path(daemon.settings["jobs"]["storage"]) / str(job.id)
            os.makedirs(root)

            logger.debug("job %d: storing jobdata.json", job.id)
            jpath = root / "jobdata.json"
            jobargs = {
                "pipeline": pip.model_dump(),
                "payload": job.payload.model_dump(),
                "devices": {dn: dev.model_dump() for dn, dev in daemon.devs.items()},
                "job": dict(id=job.id, path=str(root)),
            }
            with jpath.open("w", encoding="UTF-8") as of:
                json.dump(jobargs, of, indent=1)

            logger.debug("job %d: reserving pipeline %s", job.id, pip.name)
            params = dict(jobid=job.id, ready=False, name=pip.name)
            req.send_pyobj(dict(cmd="pipeline", params=params))
            ret = req.recv_pyobj()
            if not ret.success:
                logger.error("job %d: could not set params %s", job.id, params)
                continue
            else:
                pip.ready = False

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

            logger.debug("job %d: setting launched_at")
            params = dict(launched_at=str(datetime.now(timezone.utc)))
            job = jobdb.update_job_id(jobid, params, dbpath)
            logger.info(
                "job %d: launched on pip '%s' and path '%s'", job.id, pip.name, jpath
            )
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
    req: zmq.Socket = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    lppargs = dict(endpoint=f"tcp://127.0.0.1:{port}", context=context)
    while getattr(thread, "do_run"):
        logger.debug("tick")
        msg = dict(cmd="status", sender=f"{__name__}.manager")
        ret, req = lpp.comm(req, msg, **lppargs)
        if req.closed:
            break
        elif ret.success is False:
            logger.critical("tomato-daemon is not running: %s", ret.msg)
            break
        daemon: Daemon = ret.data
        dbpath = daemon.settings["jobs"]["dbpath"]
        manage_running_pips(daemon.pips, dbpath, req)
        matched_pips = check_queued_jobs(
            daemon.pips, daemon.cmps, daemon.drvs, dbpath, context
        )
        action_queued_jobs(daemon, matched_pips, req, dbpath)
        time.sleep(timeout / 1e3)
    req.close()
    logger.info("instructed to quit")


def tomato_job() -> None:
    """
    The function called when `tomato-job` is executed.

    This function is responsible for managing all activities of a single job, including
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
    context = zmq.Context()

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
    ret = job_main_loop(context, args.port, job, pip, logpath)
    logger.info("==============================")

    job.completed_at = str(datetime.now(timezone.utc))

    if ret is None:
        job.status = "c"
    else:
        job.status = "ce"
    logger.info("writing final data to a NetCDF file")
    merge_netcdfs(job)
    logger.info("job finished with status '%s', updating job db", job.status)
    params = dict(status=job.status, completed_at=job.completed_at)
    job = jobdb.update_job_id(job.id, params, args.dbpath)
    logger.debug(f"{job=}")
    logger.info("exiting tomato-job")


def job_thread(
    tasks: list[Task],
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
    thread = current_thread()
    sender = f"{__name__}.job_thread({thread.ident:5d})"
    logger = logging.getLogger(sender)
    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{driver.port}")
    lppargs = dict(
        endpoint=f"tcp://127.0.0.1:{driver.port}", context=context, sender=sender
    )

    logger.info(
        "%s: job thread of %s attached to tomato-daemon", component.role, component.name
    )

    kwargs = dict(address=component.address, channel=component.channel)

    datapath = Path(jobpath) / f"{component.role}.pkl"
    logger.debug("%s: processing tasks on component %s", component.role, component.name)
    for ti, task in enumerate(tasks):
        taskid = f"{component.role}:{ti}"
        if task.task_name is not None:
            taskid += f":{task.task_name!r}"
        thread.current_task = task
        logger.info("%s: processing task", taskid)

        # Hold while start contidions are not met
        while True:
            if task.start_with_task_name is None:
                break
            elif task.start_with_task_name in thread.started_task_names:
                break
            else:
                logger.debug(
                    "%s: waiting for task_name '%s'", taskid, task.start_with_task_name
                )
                time.sleep(1e-1)

        # Hold while component task_list is not ready
        while True:
            logger.debug(
                "%s: polling component %s for task readiness", taskid, component.name
            )
            msg = dict(cmd="task_status", params={**kwargs})
            ret, req = lpp.comm(req, msg, **lppargs)
            if ret.success and ret.data["can_submit"]:
                break
            elif req.closed:
                thread.crashed = True
                sys.exit()
            logger.warning(
                "%s: cannot submit onto component %s, waiting", taskid, component.name
            )
            time.sleep(1e-1)

        # Send task to component
        logger.info("%s: sending task to component %s", taskid, component.name)
        msg = dict(cmd="task_start", params={"task": task, **kwargs})
        ret, req = lpp.comm(req, msg, **lppargs)
        if req.closed:
            thread.crashed = True
            sys.exit()

        # Main task loop
        tP = time.perf_counter()
        while True:
            tN = time.perf_counter()

            # Poll for data every device.pollrate, save to pickle
            if tN - tP > device.pollrate:
                logger.debug("%s: polling task for data", taskid)
                msg = dict(cmd="task_data", params={**kwargs})
                ret, req = lpp.comm(req, msg, **lppargs, timeout=5000)
                if req.closed:
                    thread.crashed = True
                    sys.exit()
                elif ret.success and ret.data is not None:
                    logger.debug("%s: pickling received data", taskid)
                    ds: xr.Dataset = ret.data
                    ds.attrs["tomato_Component"] = component.model_dump_json()
                    data_to_pickle(ds, datapath, role=component.role)
                tP += device.pollrate

            # Poll for completion and correct task status
            logger.debug("%s: polling task for completion", taskid)
            msg = dict(cmd="task_status", params={**kwargs})
            ret, req = lpp.comm(req, msg, **lppargs)
            if req.closed:
                thread.crashed = True
                sys.exit()
            elif ret.success and not ret.data["running"]:
                logger.info("%s: task no longer running, break", taskid)
                break
            elif ret.success and "task" in ret.data and ret.data["task"] != task:
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
                and task.stop_with_task_name in thread.started_task_names
            ):
                logger.info("%s: task stop trigger met", taskid)
                msg = dict(cmd="task_stop", params={**kwargs})
                ret, req = lpp.comm(req, msg, **lppargs, timeout=5000)
                if req.closed:
                    thread.crashed = True
                    sys.exit()
                elif ret.success and ret.data is not None:
                    logger.debug("%s: pickling received data", taskid)
                    ds: xr.Dataset = ret.data
                    ds.attrs["tomato_Component"] = component.model_dump_json()
                    data_to_pickle(ds, datapath, role=component.role)
                break

            time.sleep(max(1e-1, (device.pollrate - (tN - tP)) / 2))

        # Store final task data, housekeeping.
        logger.info("%s: task fetching final data", taskid)
        msg = dict(cmd="task_data", params={**kwargs})
        ret, req = lpp.comm(req, msg, **lppargs, timeout=5000)
        if req.closed:
            thread.crashed = True
            sys.exit()
        elif ret.success and ret.data is not None:
            logger.debug("%s: pickling received data", taskid)
            ds: xr.Dataset = ret.data
            ds.attrs["tomato_Component"] = component.model_dump_json()
            data_to_pickle(ds, datapath, role=component.role)
        thread.completed_tasks.append(task)
        thread.current_task = None

    # Reset component at the end of the job
    logger.info(
        "%s: all tasks done on component %s, resetting", component.role, component.name
    )
    if driver.version == "1.0":
        msg = dict(cmd="dev_reset", params={**kwargs})
    else:
        msg = dict(cmd="cmp_reset", params={**kwargs})
    ret, req = lpp.comm(req, msg, **lppargs, timeout=5000)
    if req.closed:
        thread.crashed = True
        sys.exit()
    elif not ret.success:
        logger.warning("%s: could not reset component: %s", component.role, ret.msg)
    else:
        logger.info("%s: reset of component %s done", component.role, component.name)
    req.close()


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
    lppargs = dict(endpoint=f"tcp://127.0.0.1:{port}", context=context)

    while True:
        ret, req = lpp.comm(req, dict(cmd="status", sender=sender), **lppargs)
        if ret.success:
            daemon: Daemon = ret.data
        else:
            sys.exit()
        if all([drv.port is not None for drv in daemon.drvs.values()]):
            break
        else:
            logger.debug("not all tomato-drivers have a port, waiting")
            time.sleep(1)
    req.close()

    pipeline = daemon.pips[pipname]
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
            daemon=False,
        )
        threads[component.role].crashed = False
        threads[component.role].completed_tasks = []
        threads[component.role].current_task = None
        threads[component.role].started_task_names = set()
        threads[component.role].start()

    # wait until threads join or we're killed
    snapshot = job.payload.settings.snapshot
    t0 = time.perf_counter()
    started_task_names = set()
    while True:
        tN = time.perf_counter()
        if snapshot is not None and tN - t0 > snapshot.frequency:
            logger.debug("creating snapshot")
            merge_netcdfs(job, snapshot=True)
            t0 += snapshot.frequency

        # Collect and push task names
        for t in threads.values():
            if t.current_task is not None and t.current_task.task_name is not None:
                started_task_names.add(t.current_task.task_name)
        logger.debug("started task names are: %s", started_task_names)
        for t in threads.values():
            t.started_task_names.update(started_task_names)
        crashed = [t.crashed for t in threads.values()]
        joined = [t.is_alive() is False or t.crashed for t in threads.values()]
        if all(joined):
            if any(crashed):
                return 1
            else:
                return None
        else:
            # We'd like to execute this loop exactly once every second
            time.sleep(1.0 - tN % 1)
