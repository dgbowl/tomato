from typing import Callable
import psutil
import os
import multiprocessing
import time
import json
import logging
log = logging.getLogger(__name__)

from ..drivers import driver_worker
from .. import dbhandler

def _find_matching_pipelines(pipelines: dict, method: dict) -> list[str]:
    req_names = set(method.keys())
    req_capabs = []
    for k in req_names:
        for s in method[k]:
            req_capabs.append(s["name"])
    req_capabs = set(req_capabs)
    
    name_match = []
    candidates = []
    for cd in pipelines.keys():
        if req_names.intersection(set(pipelines[cd].keys())) == req_names:
            candidates.append(cd)

    matched = []
    for cd in candidates:
        capabs = []
        for k, v in pipelines[cd].items():
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

    
def job_wrapper(
    settings: dict, 
    pipelines: dict, 
    payload: dict,
    pip: str,
    jobid: int,
) -> None:

    queue = settings["queue"]
    state = settings["state"]
    pid = os.getpid()
    log.info(f"executing job '{jobid}' on pid '{pid}'")
    dbhandler.pipeline_assign_job(
        state["path"], pip, jobid, pid, type=state["type"]
    )
    dbhandler.job_set_status(queue["path"], "r", jobid, type=queue["type"])
    dbhandler.job_set_time(queue["path"], "executed_at", jobid, type=queue["type"])
    driver_worker(settings, pipelines[pip], payload, jobid)
    ready = payload.get("tomato", {}).get("unlock_when_done", False)
    dbhandler.job_set_status(queue["path"], "c", jobid, type=queue["type"])
    dbhandler.job_set_time(queue["path"], "completed_at", jobid, type=queue["type"])
    dbhandler.pipeline_reset_job(state["path"], pip, ready, type=state["type"])

def main_loop(
    settings: dict, 
    pipelines: dict
) -> None:
    qup = settings["queue"]["path"]
    qut = settings["queue"]["type"]
    stp = settings["state"]["path"]
    stt = settings["state"]["type"]
    while True:
        # check existing PIDs in state
        ret = dbhandler.pipeline_get_running(stp, type = stt)
        for pip, jobid, pid in ret:
            log.debug(f"checking PID of running job '{jobid}'")
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name():
                log.debug(f"PID of running job '{jobid}' found")
                # dbhandler.job_set_status(queue, "r", jobid)
            else:
                log.debug(f"PID of running job '{jobid}' not found")
                dbhandler.pipeline_reset_job(stp, pip, False, type = stt)
                dbhandler.job_set_status(qup, "ce", jobid, type = qut)
                dbhandler.job_set_time(qup, 'completed_at', jobid, type = qut)

        # check existing jobs in queue
        ret = dbhandler.job_get_all(qup, type = qut)
        for jobid, strpl, st in ret:
            payload = json.loads(strpl)
            if st in ["q", "qw"]:
                log.debug(f"checking whether job '{jobid}' can be matched")
                matched_pips = _find_matching_pipelines(pipelines, payload["method"])
                if len(matched_pips) > 0 and st != "qw":
                    dbhandler.job_set_status(qup, "qw", jobid, type = qut)
                log.debug(f"checking whether job '{jobid}' can be queued")
                for pip in matched_pips:
                    pipinfo = dbhandler.pipeline_get_info(stp, pip, type = stt)
                    can_queue = _pipeline_ready_sample(pipinfo, payload["sample"])
                    if can_queue:
                        p = multiprocessing.Process(
                            name=f"driver_worker_{jobid}",
                            target=job_wrapper, 
                            args=(settings, pipelines, payload, pip, jobid)
                        )
                        p.start()
                        break
        time.sleep(settings.get("main loop", 1))


        # - if jobid->status == q:
        #     find matching pipelines -> qw
        # - if jobid->status == qw:
        #     find matching pipelines
        #     find matching samples
        #     is pipeline ready -> r -> assign jobid and pid into pipeline state 

    #for pname, pvals in pipelines.items():
    #    print(f'driver_worker(settings, pvals, None): with {pname}')
    #    driver_worker(settings, pvals, None)
    
