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

#    print(req_names)
#    print(req_capabs)

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
    

def _pipeline_ready_sample(state: Callable, pip: str, sample: dict) -> bool:
    conn = state()
    cur = conn.cursor()
    cur.execute(
        f"SELECT sampleid, ready FROM state WHERE pipeline = '{pip}'"
    )
    ret = cur.fetchall()
    conn.close()
    for sampleid, ready in ret:
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
    queue = dbhandler.get_queue_func(
        settings["queue"]["path"], type = settings["queue"]["type"]
    )
    state = dbhandler.get_state_func(
        settings["state"]["path"], type = settings["state"]["type"]
    )
    pid = os.getpid()
    log.info(f"executing job '{jobid}' on pid '{pid}'")
    dbhandler.pipeline_assign_job(state, pip, jobid, pid)
    dbhandler.job_set_status(queue, "r", jobid)
    dbhandler.job_set_time(queue, "executed_at", jobid)
    driver_worker(settings, pipelines[pip], payload, jobid)
    ready = payload.get("tomato", {}).get("unlock_when_done", False)
    dbhandler.job_set_status(queue, "c", jobid)
    dbhandler.job_set_time(queue, "completed_at", jobid)
    dbhandler.pipeline_reset_job(state, pip, ready)

def main_loop(
    settings: dict, 
    pipelines: dict, 
    queue: Callable, 
    state: Callable
) -> None:
    while True:
        # check existing PIDs in state
        ret = dbhandler.pipeline_get_running(state)
        for pip, jobid, pid in ret:
            log.debug(f"checking PID of running job '{jobid}'")
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name():
                log.debug(f"PID of running job '{jobid}' found")
                # dbhandler.job_set_status(queue, "r", jobid)
            else:
                log.debug(f"PID of running job '{jobid}' not found")
                dbhandler.pipeline_reset(state, pip, False)
                dbhandler.job_set_status(queue, "ce", jobid)
                dbhandler.job_set_time(queue, 'completed_at', jobid)

        # check existing jobs in queue
        ret = dbhandler.job_get_all(queue)
        for jobid, strpl, st in ret:
            payload = json.loads(strpl)
            if st in ["q", "qw"]:
                log.debug(f"checking whether job '{jobid}' can be matched")
                matched_pips = _find_matching_pipelines(pipelines, payload["method"])
                if len(matched_pips) > 0 and st != "qw":
                    dbhandler.job_set_status(queue, "qw", jobid)
                log.debug(f"checking whether job '{jobid}' can be queued")
                for pip in matched_pips:
                    can_queue  = _pipeline_ready_sample(state, pip, payload["sample"])
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
    
