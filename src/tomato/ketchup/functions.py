import os
import json
import yaml
import logging
import signal
import psutil
import time
from argparse import Namespace
from pathlib import Path
from dgbowl_schemas.tomato import to_payload
from .. import setlib
from .. import dbhandler
from ..drivers import yadg_funcs


log = logging.getLogger(__name__)


def submit(args: Namespace) -> None:
    """
    Job submission function. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] submit <payload> [--jobname JOBNAME]

    Attempts to open the ``yaml/json`` file specified in the ``<payload>`` argument,
    and submit it to tomato's queue.

    The supplied :class:`argparse.Namespace` has to contain the path to the ``payload``.
    Optional arguments include an optional ``--jobname/-j`` parameter for supplying a
    job name for the queue, the verbose/quiet switches (``-v/-q``) and the testing
    switch (``-t``).

    Examples
    --------

    >>> # Submit a job:
    >>> ketchup submit .\dummy_random_2_0.1.yml
    jobid: 2
    jobname: null

    >>> # Increased verbosity:
    >>> ketchup -v submit .\dummy_random_2_0.1.yml
    INFO:tomato.ketchup.functions:Output path not set. Setting output path to 'C:\[...]'
    INFO:tomato.ketchup.functions:queueing 'payload' into 'queue'
    INFO:tomato.dbhandler.sqlite:inserting a new job into 'state'
    jobid: 4
    jobname: null

    >>> # With a job name:
    >>> ketchup submit .\dummy_random_2_0.1.yml -j dummy_random_2_0.1
    jobid: 5
    jobname: dummy_random_2_0.1

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    queue = settings["queue"]
    if os.path.exists(args.payload) and os.path.isfile(args.payload):
        log.debug(f"attempting to open Payload at '{args.payload}'")
    else:
        log.error(f"Payload file '{args.payload} not found.")
        return None

    with open(args.payload, "r") as infile:
        if args.payload.endswith("json"):
            pldict = json.load(infile)
        elif args.payload.endswith("yml") or args.payload.endswith("yaml"):
            pldict = yaml.full_load(infile)
        else:
            log.error("Payload file name must end with one of: {json, yml, yaml}.")
            return None
    payload = to_payload(**pldict)
    log.debug("Payload=Payload(%s)", payload)
    if payload.tomato.output.path is None:
        cwd = str(Path().resolve())
        log.info("Output path not set. Setting output path to '%s'", cwd)
        payload.tomato.output.path = cwd
    if hasattr(payload.tomato, "snapshot"):
        if payload.tomato.snapshot is not None:
            if payload.tomato.snapshot.path is None:
                cwd = str(Path().resolve())
                log.info("Snapshot path not set. Setting output path to '%s'", cwd)
                payload.tomato.snapshot.path = cwd
    pstr = payload.json()
    log.info("queueing 'payload' into 'queue'")
    jobid = dbhandler.queue_payload(
        queue["path"], pstr, type=queue["type"], jobname=args.jobname
    )
    print(f"jobid: {jobid}")
    print(f"jobname: {'null' if args.jobname is None else args.jobname}")


def status(args: Namespace) -> None:
    """
    Job, queue and pipeline status query function. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] status
        ketchup [-t] [-v] [-q] status [queue|state]
        ketchup [-t] [-v] [-q] status <jobid>

    The :class:`argparse.Namespace` has to contain the ``<jobid>`` the status of
    which is supposed to be queried. Alternatively, the status of the ``queue``
    or ``state`` of tomato can be queried. Optional arguments include the verbose/
    quiet switches (``-v/-q``) and the testing switch (``-t``).

    Examples
    --------

    >>> # Get pipeline status of tomato:
    >>> ketchup status
    pipeline             ready jobid  (PID)     sampleid
    ===================================================================
    dummy-10             no    3      1035      dummy_sequential_1_0.05
    dummy-5              no    None             None

    >>> # Get queue status with queued & running jobs:
    >>> ketchup status queue
    jobid  status (PID)     pipeline
    ==========================================
    3      r      1035      dummy-10
    4      q

    >>> # Get queue status with all jobs:
    >>> ketchup -v status queue
    jobid  jobname              status (PID)     pipeline
    ==============================================================
    1      None                 c
    2      custom_name          cd
    3      None                 r      1035      dummy-10
    4      other_name           q

    .. note::

        Calling ``ketchup status`` with a single ``jobid`` will return a ``yaml``
        :class:`list`, even though status of only one element was queried.

    >>> # Get status of a given job
    >>> ketchup status 1
    - jobid: 1
      jobname: null
      status:  c
      submitted: 2022-06-02 06:49:00.578619+00:00
      executed: 2022-06-02 06:49:02.966775+00:00
      completed: 2022-06-02 06:49:08.229213+00:00

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    queue = settings["queue"]

    if "state" in args.jobid:
        pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
        print(
            f"{'pipeline':20s} {'ready':5s} {'jobid':6s} {'(PID)':9s} {'sampleid':20s} "
        )
        print("=" * 67)
        for pip in pips:
            sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
                state["path"], pip, state["type"]
            )
            rstr = "yes" if ready else "no"
            job = f"{str(jobid):6s} ({pid})" if jobid is not None else str(jobid)
            print(f"{pip:20s} {rstr:5s} {job:16s} {str(sampleid):20s}")
    elif "queue" in args.jobid:
        jobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        print(
            f"{'jobid':6s} {'jobname':20s} {'status':6s} {'(PID)':9s} {'pipeline':20s}"
        )
        print("=" * (7 + 21 + 7 + 10 + 20))
        for jobid, jobname, payload, status in jobs:
            if status.startswith("q"):
                print(f"{str(jobid):6s} {str(jobname):20s} {status}")
            elif status.startswith("r"):
                for pip, pjobid, pid in running:
                    if pjobid == jobid:
                        print(
                            f"{str(jobid):6s} {str(jobname):20s} "
                            f"{status:6s} {str(pid):7s} {pip:20s}"
                        )
            elif status.startswith("c") and args.verbose - args.quiet > 0:
                print(f"{str(jobid):6s} {str(jobname):20s} {status:6s}")
    else:
        for jobid in args.jobid:
            try:
                jobid = int(jobid)
            except:
                logging.error("could not parse provided jobid: '%s'", jobid)
                return 1
            ji = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
            if ji is None:
                log.error("job with jobid '%s' does not exist.", jobid)
                return None
            jobname, payload, status, submitted_at, executed_at, completed_at = ji
            print(f"- jobid: {jobid}")
            print(f"  jobname: {'null' if jobname is None else jobname}")
            print(f"  status: {status}")
            print(f"  submitted: {submitted_at}")
            if status.startswith("r") or status.startswith("c"):
                print(f"  executed: {executed_at}")
                running = dbhandler.pipeline_get_running(
                    state["path"], type=state["type"]
                )
                for pipeline, pjobid, pid in running:
                    if pjobid == jobid:
                        print(f"  pipeline: {pipeline}")
                        print(f"  pid: {pid}")
                        break
            if status.startswith("c"):
                print(f"  completed: {completed_at}")


def cancel(args: Namespace) -> None:
    """
    Job cancellation function. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] cancel <jobid>

    The :class:`argparse.Namespace` has to contain the ``<jobid>`` of the job to be
    cancelled. Optional arguments include the verbose/quiet switches (``-v/-q``) and
    the testing switch (``-t``).

    .. note::

        The :func:`~ketchup.functions.cancel` only sets the status of the running
        job to ``rd``; the actual job cancellation is performed in the
        :func:`tomato.daemon.main.main_loop`.

    Examples
    --------

    >>> # Cancel a job:
    >>> ketchup cancel 1

    .. warning::

        Cancelling a running job will generate a warning. Output FAIR data should be
        created as requested in the ``<payload>``.

    >>> # Cancel a running job:
    >>> ketchup cancel 1
    WARNING:tomato.ketchup.functions:cancelling a running job 1 with pid 17584

    .. note::

        Cancelling a completed job will do nothing.

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    queue = settings["queue"]
    jobid = int(args.jobid)
    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    if jobinfo is None:
        log.error("job with jobid '%s' does not exist.", jobid)
        return None
    status = jobinfo[2]
    log.debug(f"found job {jobid} with status '{status}'")
    if status in {"q", "qw"}:
        log.info(f"setting job {jobid} to status 'cd'")
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
    elif status == "r":
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        for pip, pjobid, pid in running:
            if pjobid == jobid:
                log.info(f"setting job {jobid} to status 'rd'")
                dbhandler.job_set_status(queue["path"], "rd", jobid, type=queue["type"])


def load(args: Namespace) -> None:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] load <samplename> <pipeline>

    Assigns the sample with the provided ``samplename`` into the ``pipeline``.
    Checks whether the pipeline exists and whether it is empty before loading
    sample.

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]

    log.debug(f"checking whether pipeline '{args.pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert args.pipeline in pips, f"pipeline '{args.pipeline}' not found."

    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], args.pipeline, type=state["type"]
    )
    if sampleid is not None:
        log.warning(f"pipeline '{args.pipeline}' is not empty. Aborting.")
        return None

    log.info(f"loading sample '{args.sample}' into pipeline '{args.pipeline}'")
    dbhandler.pipeline_load_sample(
        state["path"], args.pipeline, args.sample, type=state["type"]
    )


def eject(args: Namespace) -> None:
    """
    Eject a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] eject <pipeline>

    Marks the ``pipeline`` as empty. Checks whether the pipeline exists, and
    whether it is currently running.

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]

    log.debug(f"checking whether pipeline '{args.pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert args.pipeline in pips, f"pipeline '{args.pipeline}' not found."

    log.debug(f"checking if pipeline '{args.pipeline}' is running.")
    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], args.pipeline, state["type"]
    )

    if sampleid is not None:
        assert jobid is None and pid is None, (
            "cannot remove a sample" " from a running pipeline"
        )
        log.info(f"ejecting sample '{sampleid}' from pipeline '{args.pipeline}'")
        dbhandler.pipeline_eject_sample(
            state["path"], args.pipeline, type=state["type"]
        )
    else:
        log.info(f"pipeline '{args.pipeline}' is already empty")


def ready(args):
    """
    Mark pipeline as ready. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] ready <pipeline>

    Marks the ``pipeline`` as ready. Checks whether the pipeline exists, and
    whether it is currently running.

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]

    log.debug(f"checking whether pipeline '{args.pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert args.pipeline in pips, f"pipeline '{args.pipeline}' not found."

    log.debug(f"checking if pipeline '{args.pipeline}' is running.")
    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], args.pipeline, state["type"]
    )

    if jobid is None and pid is None:
        log.info(f"marking pipeline '{args.pipeline}' as ready.")
        dbhandler.pipeline_reset_job(state["path"], args.pipeline, True, state["type"])
    else:
        log.warning(f"cannot mark pipeline as ready: job '{jobid}' is running.")


def snapshot(args: Namespace) -> None:
    """
    Create a snapshot of job data. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] snapshot <jobid>

    Requests an up-to-date snapshot of the data of the job identified by ``jobid``.
    Checks whether the job is running, raises a warning if job has been finished.

    Examples
    --------

    >>> # Create a snapshot in current working directory:
    >>> ketchup snapshot 1
    >>> ls
    snapshot.1.json
    snapshot.1.zip

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state, queue = settings["state"], settings["queue"]
    jobid = int(args.jobid)

    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    if jobinfo is None:
        log.error("job with jobid '%s' does not exist.", jobid)
        return None
    status = jobinfo[2]

    if status.startswith("q"):
        log.error(
            "job with jobid '%s' is not yet running. Cannot create snapshot.", jobid
        )
        return
    elif status.startswith("c"):
        log.warning(
            "job with jobid '%s' has been completed. Will create snapshot.", jobid
        )
        pass
    elif status.startswith("r"):
        log.debug("job with jobid '%s' is running. Will create snapshot.", jobid)

    jobdir = os.path.join(queue["storage"], f"{jobid}")
    log.debug("processing jobdir '%s'", jobdir)
    assert os.path.exists(jobdir) and os.path.isdir(jobdir)
    jobfile = os.path.join(jobdir, "jobdata.json")
    assert os.path.exists(jobfile) and os.path.isfile(jobfile)

    with open(jobfile, "r") as inf:
        jobdata = json.load(inf)

    method, pipeline = jobdata["payload"]["method"], jobdata["pipeline"]
    log.debug("creating a preset file '%s'", f"preset.{jobid}.json")
    preset = yadg_funcs.get_yadg_preset(method, pipeline)
    yadg_funcs.process_yadg_preset(
        preset=preset, path=".", prefix=f"snapshot.{jobid}", jobdir=jobdir
    )


def search(args: Namespace) -> None:
    """
    Search the queue for a job that matches a given jobname. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] [-c] search <jobname>

    Searches the ``queue`` for a job that matches the ``jobname``, returns the
    job status and ``jobid``. If the option ``-c/--complete`` is specified,
    the completed jobs will also be searched.

    Examples
    --------

    >>> # Create a snapshot in current working directory:
    >>> ketchup submit .\dummy_random_2_0.1.yml -j dummy_random_2_0.1
    >>> ketchup search dummy_random_2
    - jobid: 1
      jobname: dummy_random_2_0.1
      status: r

    """
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    queue = settings["queue"]

    alljobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
    for jobid, jobname, payload, status in alljobs:
        if jobname is not None and args.jobname in jobname:
            if args.complete or not status.startswith("c"):
                print(f"- jobid: {jobid}")
                print(f"  jobname: {jobname}")
                print(f"  status: {status}")
