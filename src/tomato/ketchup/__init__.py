"""
**tomato.ketchup**: command line interface to the tomato job queue
------------------------------------------------------------------
.. codeauthor:: 
    Peter Kraus

Module of functions to manage the job queue of :mod:`tomato`. Includes job management 
functions:

- :func:`submit` to submit a *job* to *queue*
- :func:`status` to query the status of tomato's *queue*, or a *job*
- :func:`cancel` to cancel a queued or kill a running *job*
- :func:`snapshot` to create an up-to-date FAIR data archive of a running *job*
- :func:`search` to find a ``jobid`` of a *job* from ``jobname``

"""
import os
import json
import logging
from pathlib import Path
import toml
import yaml
import zmq
from dgbowl_schemas.tomato import to_payload

from tomato import dbhandler
from tomato.drivers import yadg_funcs
from tomato.models import Reply

log = logging.getLogger(__name__)


def submit(*, appdir: str, payload: str, jobname: str, **_: dict) -> Reply:
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
        pass
    else:
        return Reply(success=False, msg=f"payload file {payload} not found")

    with open(payload, "r", encoding="utf-8") as infile:
        if payload.endswith("json"):
            pldict = json.load(infile)
        elif payload.endswith("yml") or payload.endswith("yaml"):
            pldict = yaml.full_load(infile)
        else:
            return Reply(
                success=False, msg="payload file must end with one of {json, yml, yaml}"
            )
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
    return Reply(
        success=True,
        msg="job submitted successfully",
        data=dict(jobid=jobid, jobname=jobname),
    )


def status(
    *,
    appdir: str,
    jobids: list[int],
    verbosity: int,
    context: zmq.Context,
    status: dict,
    **_: dict,
) -> Reply:
    """
    Job or queue status query function. Usage:

    .. code:: bash

        ketchup [-t] [-v] [-q] status
        ketchup [-t] [-v] [-q] status <jobid>

    The :class:`argparse.Namespace` has to contain the ``<jobid>`` the status of
    which is supposed to be queried. If no ``<jobid>`` is provided, the status of the
    whole ``queue`` of tomato is be queried.

    Examples
    --------

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
    running = [pip for pip in status.data if pip.jobid is not None]
    ret = []
    if len(jobids) == 0:
        jobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
        for jobid, jobname, payload, status in jobs:
            if status.startswith("q"):
                ret.append(dict(jobid=jobid, jobname=jobname, status=status))
            elif status.startswith("r"):
                for pip in running:
                    if pip.jobid == jobid:
                        ret.append(
                            dict(
                                jobid=jobid,
                                jobname=jobname,
                                status=status,
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
                for pip in running:
                    if pip.jobid == jobid:
                        retitem["pipeline"] = pip
                        break
            if status.startswith("c"):
                retitem["completed"] = completed_at
            ret.append(retitem)
    if len(ret) == 0:
        return Reply(
            success=False,
            msg="queue empty" if len(jobids) == 0 else "matching job not found",
        )
    else:
        return Reply(success=True, msg=f"status of {len(ret)} jobs returned", data=ret)


def cancel(
    *, appdir: str, jobid: int, context: zmq.Context, status: dict, **_: dict
) -> Reply:
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
    queue = settings["queue"]
    running = [pip for pip in status.data if pip.jobid is not None]
    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    if jobinfo is None:
        return Reply(success=False, msg=f"job with jobid {jobid} does not exist")
    status = jobinfo[2]
    log.debug(f"found job {jobid} with status '{status}'")
    if status in {"q", "qw"}:
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
        return Reply(success=True, msg=f"job {jobid} cancelled with status 'cd'")
    elif status == "r":
        for pip in running:
            if pip.jobid == jobid:
                dbhandler.job_set_status(queue["path"], "rd", jobid, type=queue["type"])
                return Reply(
                    success=True, msg=f"job {jobid} cancelled with status 'rd'"
                )
    elif status in {"rd", "cd"}:
        return Reply(success=False, msg=f"job {jobid} has already been cancelled")


def snapshot(*, appdir: str, jobid: int, **_: dict) -> Reply:
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
        return Reply(success=False, msg=f"job {jobid} does not exist")
    status = jobinfo[2]

    if status.startswith("q"):
        return Reply(
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
    return Reply(success=True, msg=f"snapshot for job {jobid} created successfully")


def search(
    *,
    appdir: str,
    jobname: str,
    **_: dict,
) -> Reply:
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
            ret.append(dict(jobid=jobid, jobname=jobn, status=status))
    if len(ret) > 0:
        return Reply(
            success=True, msg=f"job with jobname matching {jobname} found", data=ret
        )
    else:
        return Reply(success=False, msg=f"no job with jobname matching {jobname} found")
