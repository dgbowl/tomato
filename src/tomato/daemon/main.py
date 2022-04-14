from importlib import metadata
import psutil
import argparse
import os
import subprocess
import time
import json
import logging

from ..drivers import driver_worker, driver_reset
from .. import dbhandler


def _find_matching_pipelines(pipelines: list, method: dict) -> list[str]:
    req_names = set(method.keys())
    req_capabs = []
    for k in req_names:
        for s in method[k]:
            req_capabs.append(s["name"])
    req_capabs = set(req_capabs)

    candidates = []
    for cd in pipelines:
        dnames = set([dev["tag"] for dev in cd["devices"]])
        if req_names.intersection(dnames) == req_names:
            candidates.append(cd)

    matched = []
    for cd in candidates:
        capabs = []
        for v in cd["devices"]:
            capabs += v["capabilities"]
        if req_capabs.intersection(set(capabs)) == req_capabs:
            matched.append(cd)

    return matched


def _pipeline_ready_sample(ret: tuple, sample: dict) -> bool:
    sampleid, ready, jobid, pid = ret
    if ready == 0:
        return False
    else:
        if sample["name"] == sampleid:
            return True
        else:
            return False


def tomato_job() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "jobfile",
        help="Path to a ketchup-processed payload json file.",
        default=None,
    )
    args = parser.parse_args()
    
    logfile = args.jobfile.replace(".json", ".log")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s:%(levelname)-8s:%(processName)s:%(message)s',
        handlers=[
            logging.FileHandler(logfile, mode="a"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    logger.info("attempting to load jobfile '%s'", args.jobfile)
    with open(args.jobfile, "r") as infile:
        jsdata = json.load(infile)

    logger.debug("parsing data from jobfile")
    settings = jsdata["settings"]
    payload = jsdata["payload"]
    pipeline = jsdata["pipeline"]
    pip = pipeline["name"]
    jobid = jsdata["jobid"]
    queue = settings["queue"]
    state = settings["state"]
    pid = os.getpid()

    
    logger.debug(f"assigning job '{jobid}' on pid '{pid}' into pipeline '{pip}'")
    dbhandler.pipeline_assign_job(state["path"], pip, jobid, pid, type=state["type"])
    dbhandler.job_set_status(queue["path"], "r", jobid, type=queue["type"])
    dbhandler.job_set_time(queue["path"], "executed_at", jobid, type=queue["type"])

    logger.info("handing off to 'driver_worker'")
    logger.info("==============================")
    ret = driver_worker(settings, pipeline, payload, jobid, logfile)

    logger.info("==============================")
    ready = payload.get("tomato", {}).get("unlock_when_done", False)
    if ret is None:
        logger.info("job finished successfully, setting status to 'c'")
        dbhandler.job_set_status(queue["path"], "c", jobid, type=queue["type"])
    else:
        logger.info("job was terminated, setting status to 'cd'")
        dbhandler.job_set_status(queue["path"], "cd", jobid, type=queue["type"])
        logger.info("handing off to 'driver_reset'")
        logger.info("==============================")
        driver_reset(settings, pipeline)
        logger.info("==============================")
        ready = False

    logger.debug(f"setting pipeline '{pip}' as '{'ready' if ready else 'not ready'}'")
    dbhandler.pipeline_reset_job(state["path"], pip, ready, type=state["type"])
    dbhandler.job_set_time(queue["path"], "completed_at", jobid, type=queue["type"])
    


def main_loop(settings: dict, pipelines: dict) -> None:
    log = logging.getLogger(__name__)
    qup = settings["queue"]["path"]
    qut = settings["queue"]["type"]
    stp = settings["state"]["path"]
    stt = settings["state"]["type"]
    while True:
        # check existing PIDs in state
        ret = dbhandler.pipeline_get_running(stp, type=stt)
        for pip, jobid, pid in ret:
            log.debug(f"checking PID of running job '{jobid}'")
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name():
                log.debug(f"PID of running job '{jobid}' found")
                # dbhandler.job_set_status(queue, "r", jobid)
            else:
                log.debug(f"PID of running job '{jobid}' not found")
                dbhandler.pipeline_reset_job(stp, pip, False, type=stt)
                dbhandler.job_set_status(qup, "ce", jobid, type=qut)
                dbhandler.job_set_time(qup, "completed_at", jobid, type=qut)

        # check existing jobs in queue
        ret = dbhandler.job_get_all(qup, type=qut)
        for jobid, strpl, st in ret:
            payload = json.loads(strpl)
            if st in ["q", "qw"]:
                if st == "q":
                    log.debug(f"checking whether job '{jobid}' can ever be matched")
                matched_pips = _find_matching_pipelines(pipelines, payload["method"])
                if len(matched_pips) > 0 and st != "qw":
                    dbhandler.job_set_status(qup, "qw", jobid, type=qut)
                log.debug(f"checking whether job '{jobid}' can be queued")
                for pip in matched_pips:
                    pipinfo = dbhandler.pipeline_get_info(stp, pip["name"], type=stt)
                    can_queue = _pipeline_ready_sample(pipinfo, payload["sample"])
                    if can_queue:
                        dbhandler.pipeline_reset_job(stp, pip["name"], False, type=stt)
                        args = {
                            "settings": settings,
                            "pipeline": pip,
                            "payload": payload,
                            "jobid": jobid,
                        }
                        root = os.path.join(settings["queue"]["storage"], str(jobid))
                        os.makedirs(root)
                        jpath = os.path.join(root, "jobdata.json")
                        with open(jpath, "w") as of:
                            json.dump(args, of, indent=1)
                        cfs = subprocess.CREATE_NEW_PROCESS_GROUP
                        cfs |= subprocess.CREATE_NO_WINDOW
                        subprocess.Popen(
                            ["tomato_job", str(jpath)],
                            creationflags=cfs,
                        )
                        break
        time.sleep(settings.get("main loop", 1))

        # - if jobid->status == q:
        #     find matching pipelines -> qw
        # - if jobid->status == qw:
        #     find matching pipelines
        #     find matching samples
        #     is pipeline ready -> r -> assign jobid and pid into pipeline state

    # for pname, pvals in pipelines.items():
    #    print(f'driver_worker(settings, pvals, None): with {pname}')
    #    driver_worker(settings, pvals, None)
