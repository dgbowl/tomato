import os
import json
import yaml
import logging
import signal
import psutil
from pathlib import Path
from dgbowl_schemas.tomato import to_payload
from .. import setlib
from .. import dbhandler

log = logging.getLogger(__name__)


def submit(args):
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    queue = settings["queue"]

    assert os.path.exists(args.payload)
    assert os.path.isfile(args.payload)

    log.debug(f"attempting to open payload at '{args.payload}'")
    with open(args.payload, "r") as infile:
        if args.payload.endswith("json"):
            pldict = json.load(infile)
        elif args.payload.endswith("yml") or args.payload.endswith("yaml"):
            pldict = yaml.full_load(infile)
    payload = to_payload(**pldict)
    log.debug("payload=Payload(%s)", payload)
    if payload.tomato.output.path is None:
        cwd = str(Path().resolve())
        log.info("Output path not set. Setting output path to '%s'", cwd)
        payload.tomato.output.path = cwd
    pstr = payload.json()
    log.info("queueing 'payload' into 'queue'")
    dbhandler.queue_payload(queue["path"], pstr, type=queue["type"])


def status(args):
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    queue = settings["queue"]

    if args.jobid == "state":
        pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
        print(
            f"{'pipeline':20s} {'ready':5s} {'jobid':5s} {'(PID)':9s} {'sampleid':20s} "
        )
        print("=" * 65)
        for pip in pips:
            sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
                state["path"], pip, state["type"]
            )
            rstr = "yes" if ready else "no"
            job = f"{str(jobid):5s} ({pid})" if jobid is not None else str(jobid)
            print(f"{pip:20s} {rstr:5s} {job:15s} {str(sampleid):20s}")
    elif args.jobid == "queue":
        jobs = dbhandler.job_get_all(queue["path"], type=queue["type"])
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        print(f"{'jobid':6s} {'status':6s} {'pid':7s} {'pipeline':20s}")
        print("=" * 42)
        for jobid, payload, status in jobs:
            if status.startswith("q"):
                print(f"{str(jobid):6s} {status}")
            elif status.startswith("r"):
                for pip, pjobid, pid in running:
                    if pjobid == jobid:
                        print(f"{str(jobid):6s} {status:6s} {str(pid):7s} {pip:20s}")
    else:
        jobid = int(args.jobid)
        ji = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
        payload, status, sub, exe, com = ji
        print(f"job '{jobid}':")
        print(f"  - status: '{status}'")
        print(f"  - submitted at: '{sub}'")
        if status.startswith("r"):
            print(f"  - running since:'{exe}'")
            running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
            for pip, pjobid, pid in running:
                if pjobid == jobid:
                    print(f"  - on pipeline: '{pip}'")
                    print(f"  - with PID: '{pid}'")
                    break
        if status.startswith("c"):
            print(f"  - executed at:  '{exe}'")
            print(f"  - completed at: '{com}'")


def cancel(args):
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    queue = settings["queue"]
    jobid = int(args.jobid)
    jobinfo = dbhandler.job_get_info(queue["path"], jobid, type=queue["type"])
    status = jobinfo[1]
    log.debug(f"found job {jobid} with status '{status}'")
    if status in {"q", "qw"}:
        log.info(f"setting job {jobid} to status 'cd'")
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
    elif status == "r":
        running = dbhandler.pipeline_get_running(state["path"], type=state["type"])
        for pip, pjobid, pid in running:
            if pjobid == jobid:
                log.warning(f"cancelling a running job {jobid} with pid {pid}")
                proc = psutil.Process(pid=pid)
                for cp in proc.children():
                    if cp.name() in {"python", "python.exe"}:
                        for ccp in cp.children():
                            log.debug(
                                "sending SIGTERM to pid %d with name '%s'",
                                ccp.pid,
                                ccp.name()
                            )
                            ccp.send_signal(signal.SIGTERM)
                        
                    


def load(args):
    dirs = setlib.get_dirs(args.test)
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]

    log.debug(f"checking whether pipeline '{args.pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert args.pipeline in pips, f"pipeline '{args.pipeline}' not found."

    log.info(f"loading sample '{args.sample}' into pipeline '{args.pipeline}'")
    dbhandler.pipeline_load_sample(
        state["path"], args.pipeline, args.sample, type=state["type"]
    )


def eject(args):
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
