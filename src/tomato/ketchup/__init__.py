"""
.. codeauthor::
    Peter Kraus

Module of functions to manage the job queue of :mod:`tomato`. Includes job management functions:

- :func:`submit` to submit a *job* to *queue*
- :func:`status` to query the status of tomato's *queue*, or a *job*
- :func:`cancel` to cancel a queued or kill a running *job*
- :func:`snapshot` to create an up-to-date FAIR data archive of a running *job*
- :func:`search` to find a ``jobid`` of a *job* from ``jobname``

.. warning::

    This module interacts with the job sqlite database directly. This means that users submitting jobs to tomato must have write access to the job database file.

"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dgbowl_schemas.tomato import to_payload
from packaging.version import Version

import tomato.daemon.jobdb as jobdb
from tomato.daemon.io import merge_netcdfs
from tomato.models import Daemon, Job, Payload, Reply

log = logging.getLogger(__name__)

__latest_payload__ = "2.2"


def submit(
    *,
    payload: str | Path,
    jobname: str,
    daemon: Daemon,
    **_: dict,
) -> Reply:
    """
    Job submission function.

    Attempts to open the ``yaml/json`` file specified in the ``payload`` argument,
    and submit it to tomato's queue.

    Reply contains information about the submitted job.

    Examples
    --------

    >>> # Submit a job:
    >>> ketchup submit counter_15_0.1.yml
    Success: job submitted successfully with jobid 1

    >>> # Submit a job with a job name:
    >>> ketchup submit counter_15_0.1.yml -j jobname_is_this
    Success: job submitted successfully with jobid 1 and jobname 'jobname_is_this'

    >>> # Submit a job with yaml output:
    >>> ketchup submit counter_15_0.1.yml -y
    data:
      completed_at: null
      connected_at: null
      id: 1
      [...]
      status: q
      submitted_at: '2024-11-17 19:39:16.972593+00:00'
    msg: job submitted successfully with jobid 1
    success: true

    """
    payload = Path(payload)
    if payload.exists() and payload.is_file():
        pass
    else:
        return Reply(success=False, msg=f"payload file {payload} not found")

    with payload.open() as inf:
        if payload.suffix == ".json":
            pldict = json.load(inf)
        elif payload.suffix in {".yml", ".yaml"}:
            pldict = yaml.full_load(inf)
        else:
            return Reply(success=False, msg="payload must be a yaml or a json file")

    payload: Payload = to_payload(**pldict)
    maxver = Version(__latest_payload__)
    while hasattr(payload, "update"):
        temp: Payload = payload.update()  # ty: ignore[call-non-callable]
        if hasattr(temp, "version"):
            if Version(temp.version) > maxver:
                break
        payload = temp

    if payload.settings.output.path is None:
        cwd = str(Path().resolve())
        log.info(f"Output path not set. Setting output path to {cwd}")
        payload.settings.output.path = cwd
    if payload.settings.snapshot is not None and payload.settings.snapshot.path is None:
        cwd = str(Path().resolve())
        log.info(f"Snapshot path not set. Setting output path to {cwd}")
        payload.settings.snapshot.path = cwd
    if payload.settings.output.repositories != ["default"]:
        for repo in payload.settings.output.repositories:
            if repo != "default" and repo not in daemon.settings["repositories"]:
                msg = f"payload specifies unknown output repository {repo!r}"
                return Reply(success=False, msg=msg, data=daemon.settings)

    log.debug("queueing 'payload' into 'queue'")
    dbpath = daemon.settings["jobs"]["dbpath"]
    dt = str(datetime.now(timezone.utc))
    params = dict(payload=payload, jobname=jobname, submitted_at=dt)
    job = jobdb.insert_job(job=Job(id=0, **params), dbpath=dbpath)  # ty: ignore[invalid-argument-type]

    msg = f"job submitted successfully with jobid {job.id}"
    if job.jobname is not None:
        msg += f" and jobname {job.jobname!r}"
    return Reply(success=True, msg=msg, data=job)


def status(
    *,
    jobids: list[int],
    daemon: Daemon,
    **_: dict,
) -> Reply:
    """
    Job status query function.

    Reply contains information about all matched jobs.

    .. note::

        Calling ``ketchup status`` with a single ``jobid`` will return a ``yaml``
        :class:`list`, even though status of only one element was queried.

    Examples
    --------

    >>> # Get status of a given job
    >>> ketchup status 1
    Success: found 1 job with status 'qw': [1]

    >>> # Get status of multiple jobs
    >>> ketchup status 1 2
    Success: found 2 job with status 'qw': [1]
             found 1 job with status 'c' : [2]

    >>> # Get status of non-existent job
    >>> ketchup status 3
    Failure: found no jobs with jobids [3]

    >>> # Get a status of a job with yaml output
    >>> ketchup status 1 -y
    data:
    - completed_at: null
      connected_at: null
      id: 1
      [...]
      status: qw
      submitted_at: '2024-11-17 17:53:46.133355+00:00'
    msg: found 1 job with status ['qw']
    success: true

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    if len(jobids) == 0:
        jobs = jobdb.get_jobs_where(where="id IS NOT NULL", dbpath=dbpath)
        if len(jobs) == 0:
            return Reply(success=False, msg="job queue is empty")
    else:
        where = f"id IN ({', '.join([str(j) for j in jobids])})"
        jobs = jobdb.get_jobs_where(where=where, dbpath=dbpath)
        if len(jobs) == 0:
            if len(jobids) == 1:
                msg = f"found no job with jobid {jobids}"
            else:
                msg = f"found no jobs with jobids {jobids}"
            return Reply(success=False, msg=msg)

    if len(jobs) == 1:
        msg = f"found {len(jobs)} job with status {[job.status for job in jobs]}"
    else:
        msg = ""
        for st in ["q", "qw", "r", "rd", "c", "cd", "ce"]:
            jobst = [j.id for j in jobs if j.status == st]
            if len(jobst) > 1:
                msg += (
                    f"found {len(jobst)} jobs with status {st!r:4s}: {jobst}\n         "
                )
            elif len(jobst) == 1:
                msg += (
                    f"found {len(jobst)} job with status {st!r:4s}: {jobst}\n         "
                )
        msg = msg.strip()
    return Reply(success=True, msg=msg, data=jobs)


def cancel(
    *,
    jobids: list[int],
    daemon: Daemon,
    **_: dict,
) -> Reply:
    """
    Job cancellation function.

    .. note::

        The :func:`~ketchup.functions.cancel` only sets the status of the running
        job to ``rd``; the actual job cancellation is performed in the
        :mod:`tomato.daemon.job` module.

    Examples
    --------

    >>> # Cancel a job:
    >>> ketchup cancel 1
    Success: job [1] cancelled successfully

    >>> # Cancel a job with yaml output:
    >>> ketchup cancel 2 -y
    data:
    - completed_at: null
      connected_at: null
      id: 2
      [...]
      status: cd
      submitted_at: '2024-03-03 15:23:50.702504+00:00'
    msg: job [2] cancelled successfully
    success: true

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    where = f"id IN ({', '.join([str(j) for j in jobids])})"
    jobs = jobdb.get_jobs_where(where=where, dbpath=dbpath)
    rjobids = {j.id for j in jobs}

    for jobid in jobids:
        if jobid not in rjobids:
            return Reply(success=False, msg=f"job with jobid {jobid} does not exist")

    data = []
    for job in jobs:
        if job.status in {"q", "qw"}:
            params = dict(status="cd")
        elif job.status in {"r"}:
            params = dict(status="rd")
        elif job.status in {"cd", "ce", "c"}:
            continue
        job = jobdb.update_job_id(id=jobid, params=params, dbpath=dbpath)
        data.append(job)

    if len(data) == 0:
        msg = "all jobs were already cancelled"
    elif len(data) == 1:
        msg = f"job {[j.id for j in data]} cancelled successfully"
    else:
        msg = f"jobs {[j.id for j in data]} cancelled successfully"
    return Reply(success=True, msg=msg, data=data)


def snapshot(
    *,
    jobids: list[int],
    daemon: Daemon,
    **_: dict,
) -> Reply:
    """
    Create a snapshot of job data.

    Requests an up-to-date snapshot of the data of the job identified by ``jobid``.
    Checks whether the job is running, raises a warning if job has been finished.

    Examples
    --------

    >>> # Create a snapshot in current working directory:
    >>> ketchup snapshot 3
    Success: snapshot for job [3] created successfully

    >>> # With yaml output:
    >>> ketchup snapshot 1 -y
    data: null
    msg: snapshot for job [1] created successfully
    success: true

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    where = f"id IN ({', '.join([str(j) for j in jobids])})"
    jobs = jobdb.get_jobs_where(where=where, dbpath=dbpath)
    rjobids = {j.id: j for j in jobs}

    for jobid in jobids:
        if jobid not in rjobids:
            return Reply(success=False, msg=f"job {jobid} does not exist")
        if rjobids[jobid].status in {"q", "qw"}:
            return Reply(success=False, msg=f"job {jobid} is still queued")

    for jobid, job in rjobids.items():
        job.snappath = f"snapshot.{jobid}.nc"
        merge_netcdfs(job, snapshot=True)
    if len(jobids) > 1:
        msg = f"snapshot for jobs {jobids} created successfully"
    else:
        msg = f"snapshot for job {jobids} created successfully"
    return Reply(success=True, msg=msg)


def search(
    *,
    jobname: str,
    daemon: Daemon,
    **_: dict,
) -> Reply:
    """
    Search the queue for a job that matches a given jobname.

    Searches the queue for a job that matches the ``jobname``, returns the
    job status and ``jobid``.

    Examples
    --------

    >>> # Search for a valid jobname
    >>> ketchup search counter
    Success: job matching 'counter' found: [1]

    >>> # Search for an invalid jobname
    >>> ketchup search nothing
    Failure: no job matching 'nothing' found

    """
    dbpath = daemon.settings["jobs"]["dbpath"]
    where = f"jobname LIKE '%{jobname}%'"
    jobs = jobdb.get_jobs_where(where=where, dbpath=dbpath)

    if len(jobs) > 0:
        if len(jobs) == 1:
            msg = f"job matching {jobname!r} found: {[j.id for j in jobs]}"
        else:
            msg = f"jobs matching {jobname!r} found: {[j.id for j in jobs]}"
        return Reply(success=True, msg=msg, data=jobs)
    else:
        return Reply(success=False, msg=f"no job matching {jobname!r} found")
