import os
import json
import yaml
import logging
import signal
import psutil
import time
import toml
from argparse import Namespace
from typing import List, Union
from pathlib import Path
from dgbowl_schemas.tomato import to_payload

from .. import setlib
from .. import dbhandler
from ..drivers import yadg_funcs


log = logging.getLogger(__name__)


def submit(
    *,
    appdir: str,
    payload: str,
    jobname: str,
    **_: dict,
) -> dict:
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
    settings = toml.load(Path(appdir) / "settings.toml")
    queue = settings["queue"]
    if os.path.exists(payload) and os.path.isfile(payload):
        log.debug(f"attempting to open Payload at '{payload}'")
    else:
        log.error(f"Payload file '{payload} not found.")
        return None

    with open(payload, "r") as infile:
        if payload.endswith("json"):
            pldict = json.load(infile)
        elif payload.endswith("yml") or payload.endswith("yaml"):
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
        queue["path"], pstr, type=queue["type"], jobname=jobname
    )
    return dict(
        success=True,
        msg="job submitted successfully",
        data=dict(jobid=jobid, jobname=jobname),
    )


def status(
    *,
    appdir: str,
    jobids: list[int],
    verbosity: int,
    **_: dict,
) -> dict:
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
    settings = toml.load(Path(appdir) / "settings.toml")
    queue = settings["queue"]
    state = settings["state"]
    ret = []
    if len(jobids) == 0:
        jobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        for jobid, jobname, payload, status in jobs:
            if status.startswith("q"):
                ret.append(dict(jobid=jobid, jobname=jobname, status=status))
            elif status.startswith("r"):
                for pip, pjobid, pid in running:
                    if pjobid == jobid:
                        ret.append(
                            dict(
                                jobid=jobid,
                                jobname=jobname,
                                status=status,
                                pid=pid,
                                pipeline=pip,
                            )
                        )
            elif status.startswith("c") and verbosity > 0:
                ret.append(dict(jobid=jobid, jobname=jobname, status=status))
    else:
        for jobid in jobids:
            ji = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
            if ji is None:
                log.error("job with jobid '%s' does not exist.", jobid)
                return []
            jobname, payload, status, submitted_at, executed_at, completed_at = ji
            retitem = dict(
                jobid=jobid, jobname=jobname, status=status, submitted=submitted_at
            )
            if status.startswith("r") or status.startswith("c"):
                retitem["executed"] = executed_at
                running = dbhandler.pipeline_get_running(
                    state["path"], type=state["type"]
                )
                for pipeline, pjobid, pid in running:
                    if pjobid == jobid:
                        retitem["pipeline"] = pipeline
                        retitem["pid"] = pid
                        break
            if status.startswith("c"):
                retitem["completed"] = completed_at
            ret.append(retitem)
    if len(ret) == 0:
        return dict(
            success=False,
            msg="queue empty" if len(jobids) == 0 else "matching job not found",
        )
    else:
        return dict(success=True, msg=f"status of {len(ret)} jobs returned", data=ret)


def cancel(
    *,
    appdir: str,
    jobid: int,
    **_: dict,
) -> dict:
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
    settings = toml.load(Path(appdir) / "settings.toml")
    state = settings["state"]
    queue = settings["queue"]
    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    if jobinfo is None:
        return dict(success=False, msg=f"job with jobid {jobid} does not exist")
    status = jobinfo[2]
    log.debug(f"found job {jobid} with status '{status}'")
    if status in {"q", "qw"}:
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
        return dict(success=True, msg=f"job {jobid} cancelled with status 'cd'")
    elif status == "r":
        print(f"Status is R, cancelling")
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        for pip, pjobid, pid in running:
            print(f"{pip=} {pjobid=} {pid=}")
            if pjobid == jobid:
                dbhandler.job_set_status(queue["path"], "rd", jobid, type=queue["type"])
                return dict(success=True, msg=f"job {jobid} cancelled with status 'rd'")
    elif status in {"rd", "cd"}:
        return dict(success=False, msg=f"job {jobid} has already been cancelled")


def load(
    *,
    appdir: str,
    pipeline: str,
    sample: str,
    **_: dict,
) -> dict:
    """
    Load a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] load <samplename> <pipeline>

    Assigns the sample with the provided ``samplename`` into the ``pipeline``.
    Checks whether the pipeline exists and whether it is empty before loading
    sample.

    """
    settings = toml.load(Path(appdir) / "settings.toml")
    state = settings["state"]

    log.debug(f"checking whether pipeline '{pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert pipeline in pips, f"pipeline '{pipeline}' not found."

    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], pipeline, type=state["type"]
    )
    if sampleid is not None:
        return dict(success=False, msg=f"pipeline {pipeline} is not empty, aborting")

    dbhandler.pipeline_load_sample(state["path"], pipeline, sample, type=state["type"])
    return dict(success=True, msg=f"loaded {sample} into {pipeline}")


def eject(*, appdir: str, pipeline: str, **_: dict) -> dict:
    """
    Eject a sample into a pipeline. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] eject <pipeline>

    Marks the ``pipeline`` as empty. Checks whether the pipeline exists, and
    whether it is currently running.

    """
    settings = toml.load(Path(appdir) / "settings.toml")
    state = settings["state"]

    log.debug(f"checking whether pipeline '{pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert pipeline in pips, f"pipeline '{pipeline}' not found."

    log.debug(f"checking if pipeline '{pipeline}' is running.")
    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], pipeline, state["type"]
    )

    if sampleid is not None:
        if jobid is not None or pid is not None:
            return dict(
                success=False, msg=f"cannot remove a sample from a running pipeline"
            )
        dbhandler.pipeline_eject_sample(state["path"], pipeline, type=state["type"])
        return dict(success=True, msg=f"ejected {sampleid} from {pipeline}")
    else:
        return dict(success=True, msg=f"pipeline {pipeline} already empty")
        log.info(f"pipeline '{pipeline}' is already empty")


def ready(*, appdir: str, pipeline: str, **_: dict) -> dict:
    """
    Mark pipeline as ready. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] ready <pipeline>

    Marks the ``pipeline`` as ready. Checks whether the pipeline exists, and
    whether it is currently running.

    """
    settings = toml.load(Path(appdir) / "settings.toml")
    state = settings["state"]

    log.debug(f"checking whether pipeline '{pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert pipeline in pips, f"pipeline '{pipeline}' not found."

    log.debug(f"checking if pipeline '{pipeline}' is running.")
    sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
        state["path"], pipeline, state["type"]
    )

    if jobid is None and pid is None:
        dbhandler.pipeline_reset_job(state["path"], pipeline, True, state["type"])
        return dict(success=True, msg=f"pipeline {pipeline} marked as ready")
    else:
        return dict(
            success=False,
            msg=f"cannot mark {pipeline} as ready, job {jobid} is running",
        )


def snapshot(*, appdir: str, jobid: int, **_: dict) -> dict:
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
    settings = toml.load(Path(appdir) / "settings.toml")
    state, queue = settings["state"], settings["queue"]

    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    if jobinfo is None:
        return dict(success=False, msg=f"job {jobid} does not exist")
    status = jobinfo[2]

    if status.startswith("q"):
        return dict(
            success=False, msg=f"job {jobid} is not yet running, cannot create snapshot"
        )

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
    return dict(success=True, msg=f"snapshot for job {jobid} created successfully")


def search(
    *,
    appdir: str,
    jobname: str,
    **_: dict,
) -> list[dict]:
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
    settings = toml.load(Path(appdir) / "settings.toml")
    queue = settings["queue"]

    alljobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
    ret = []
    for jobid, jobn, payload, status in alljobs:
        if jobn is not None and jobname in jobn:
            if status.startswith("c"):
                ret.append(dict(jobid=jobid, jobname=jobname, status=status))

    return ret
