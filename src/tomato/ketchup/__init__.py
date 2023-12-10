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
import json
import logging
from pathlib import Path
import yaml
import zmq
from dgbowl_schemas.tomato import to_payload

from tomato.drivers import yadg_funcs
from tomato.models import Reply, Daemon

log = logging.getLogger(__name__)


def submit(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    payload: str,
    jobname: str,
    **_: dict,
) -> Reply:
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
    >>> ketchup submit dummy_random_2_0.1.yml
    jobid: 2
    jobname: null

    >>> # Increased verbosity:
    >>> ketchup -v submit dummy_random_2_0.1.yml
    INFO:tomato.ketchup.functions:Output path not set. Setting output path to '[...]'
    INFO:tomato.ketchup.functions:queueing 'payload' into 'queue'
    INFO:tomato.dbhandler.sqlite:inserting a new job into 'state'
    jobid: 4
    jobname: null

    >>> # With a job name:
    >>> ketchup submit dummy_random_2_0.1.yml -j dummy_random_2_0.1
    jobid: 5
    jobname: dummy_random_2_0.1

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

    payload = to_payload(**pldict)
    if payload.tomato.output.path is None:
        cwd = str(Path().resolve())
        log.info(f"Output path not set. Setting output path to {cwd}")
        payload.tomato.output.path = cwd
    if hasattr(payload.tomato, "snapshot"):
        if payload.tomato.snapshot is not None and payload.tomato.snapshot.path is None:
            cwd = str(Path().resolve())
            log.info(f"Snapshot path not set. Setting output path to {cwd}")
            payload.tomato.snapshot.path = cwd

    log.info("queueing 'payload' into 'queue'")
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    params = dict(payload=payload, jobname=jobname)
    req.send_pyobj(dict(cmd="job", id=None, params=params))
    ret = req.recv_pyobj()
    if ret.success:
        return Reply(success=True, msg="job submitted successfully", data=ret.data)
    else:
        return Reply(success=False, msg="unknown error", data=ret.data)


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    verbosity: int,
    jobids: list[int],
    status: Daemon,
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
    jobs = status.data.jobs
    if len(jobs) == 0:
        return Reply(success=False, msg="job queue is empty")
    elif len(jobids) == 0:
        return Reply(success=True, msg=f"found {len(jobs)} queued jobs", data=jobs)
    else:
        rets = {job.id: job for job in jobs.values() if job.id in jobids}
        return Reply(success=True, msg=f"found {len(rets)} queued jobs", data=rets)


def cancel(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    jobids: list[int],
    status: Daemon,
    **_: dict,
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
    jobs = status.data.jobs
    for jobid in jobids:
        if jobid not in jobs:
            return Reply(success=False, msg=f"job with jobid {jobid} does not exist")

    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{port}")
    data = {}
    for jobid in jobids:
        if jobs[jobid].status in {"q", "qw"}:
            params = dict(status="cd")
        elif jobs[jobid].status in {"r"}:
            params = dict(status="rd")
        elif jobs[jobid].status in {"cd", "ce"}:
            continue
        req.send_pyobj(dict(cmd="job", id=jobid, params=params))
        ret = req.recv_pyobj()
        if ret.success:
            data[jobid] = ret.data
        else:
            return Reply(success=False, msg="unknown error", data=ret.data)
    return Reply(success=True, msg="cancelled jobs successfully", data=data)


def snapshot(
    *,
    jobids: list[int],
    status: Daemon,
    **_: dict,
) -> Reply:
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
    jobs = status.data.jobs
    for jobid in jobids:
        if jobid not in jobs:
            return Reply(success=False, msg=f"job {jobid} does not exist")
        if jobs[jobid].status in {"q", "qw"}:
            return Reply(success=False, msg=f"job {jobid} is still queued")

    jobdir = Path(status.data.settings["jobs"]["storage"])
    for jobid in jobids:
        root = jobdir / str(jobid)
        assert root.exists() and root.is_dir()
        jobfile = root / "jobdata.json"
        assert jobfile.exists() and jobfile.is_file()
        with jobfile.open() as inf:
            jobdata = json.load(inf)
        log.debug("creating a preset file '%s'", f"preset.{jobid}.json")
        preset = yadg_funcs.get_yadg_preset(
            jobdata["payload"]["method"], jobdata["pipeline"], jobdata["devices"]
        )
        yadg_funcs.process_yadg_preset(
            preset=preset, path=".", prefix=f"snapshot.{jobid}", jobdir=str(jobdir)
        )
    return Reply(success=True, msg=f"snapshot for job(s) {jobids} created successfully")


def search(
    *,
    jobname: str,
    status: Daemon,
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
    >>> ketchup submit dummy_random_2_0.1.yml -j dummy_random_2_0.1
    >>> ketchup search dummy_random_2
    - jobid: 1
      jobname: dummy_random_2_0.1
      status: r

    """
    jobs = status.data.jobs
    ret = {}
    for jobid, job in jobs.items():
        if job.jobname is not None and jobname in job.jobname:
            ret[jobid] = job
    if len(ret) > 0:
        return Reply(success=True, msg=f"jobs matching {jobname!r} found", data=ret)
    else:
        return Reply(success=False, msg=f"no job matching {jobname!r} found")
