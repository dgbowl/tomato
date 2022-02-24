import os
import json
import yaml
import logging
from .. import setlib
from .. import dbhandler

log = logging.getLogger(__name__)


def submit(args):
    dirs = setlib.get_dirs()
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    queue = settings["queue"]

    assert os.path.exists(args.payload)
    assert os.path.isfile(args.payload)
    
    log.debug(f"attempting to open payload at '{args.payload}'")
    with open(args.payload, "r") as infile:
        if args.payload.endswith("json"):
            payload = json.load(infile)
        elif args.payload.endswith("yml") or args.payload.endswith("yaml"):
            payload = yaml.full_load(infile)
    pstr = json.dumps(payload)
    log.info("queueing 'payload' into 'queue'")
    dbhandler.queue_payload(queue["path"], pstr, type = queue["type"])


def status(args):
    dirs = setlib.get_dirs()
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    queue = settings["queue"]

    if args.jobid == "queue":
        pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
        print(f"{'pipeline':20s} {'ready':5s} {'jobid (PID)':12s} {'sampleid':20s}")
        print("="*60)
        for pip in pips:
            sampleid, ready, jobid, pid = dbhandler.pipeline_get_info(
                state["path"], pip, state["type"]
            )
            rstr = 'yes' if ready else 'no'
            job = f"{jobid} ({pid})" if jobid is not None else str(jobid)
            print(f"{pip:20s} {rstr:5s} {job:12s} {str(sampleid):20s}")
    else:
        jobid = int(args.jobid)
        print(f"printing status of job '{jobid}' not yet implemented")


def stop(args):
    dirs = setlib.get_dirs()
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]


def load(args):
    dirs = setlib.get_dirs()
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
    dirs = setlib.get_dirs()
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
    dirs = setlib.get_dirs()
    settings = setlib.get_settings(dirs.user_config_dir, dirs.user_data_dir)
    state = settings["state"]
    
    log.debug(f"checking whether pipeline '{args.pipeline}' exists.")
    pips = dbhandler.pipeline_get_all(state["path"], type=state["type"])
    assert args.pipeline in pips, f"pipeline '{args.pipeline}' not found."

    log.info(f"marking pipeline '{args.pipeline}' as ready.")
    dbhandler.pipeline_reset_job(state["path"], args.pipeline, True, state["type"])