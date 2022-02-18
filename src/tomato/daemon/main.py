from typing import Callable
import textwrap
import psutil
import os
import time
import json
from datetime import datetime, timezone
import logging
log = logging.getLogger(__name__)

from ..drivers import driver_worker

def _sql_job_set_status(queue: Callable, st: str, jobid: int) -> None:
    conn = queue()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queue SET status = '{st}' WHERE jobid = {jobid}"
    )
    conn.commit()
    conn.close()


def _sql_job_set_time(queue: Callable, tcol: str, jobid: int) -> None:
    ts = str(datetime.now(timezone.utc))
    conn = queue()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queue SET {tcol} = '{ts}' WHERE jobid = {jobid}"
    )
    conn.commit()
    conn.close()


def _sql_pip_reset(state: Callable, pip: str) -> None:
    conn = state()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE state SET pid = NULL, jobid = NULL WHERE pipeline = '{pip}'"
    )
    conn.commit()
    conn.close()


def _sql_pip_assign(state: Callable, pip: str, jobid: int, pid: int) -> None:
    conn = state()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE state SET pid = {pid}, jobid = {jobid}, ready = 0 WHERE pipeline = '{pip}'"
    )
    conn.commit()
    conn.close()


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

    


def main_loop(
    settings: dict, 
    pipelines: dict, 
    queue: Callable, 
    state: Callable
) -> None:

    while True:
        # check existing PIDs in state
        conn = state()
        cur = conn.cursor()
        cur.execute(
            "SELECT pipeline, jobid, pid FROM state WHERE pid IS NOT NULL;"
        )
        ret = cur.fetchall()
        conn.close()
        for pip, jobid, pid in ret:
            log.debug(f"checking PID of running job '{jobid}'")
            print(pip, jobid, pid)
            if psutil.pid_exists(pid) and "tworker" in psutil.Process(pid).name():
                log.debug(f"PID of running job '{jobid}' found")
                _sql_job_set_status(queue, "r", jobid)
            else:
                log.debug(f"PID of running job '{jobid}' not found")
                _sql_pip_reset(state, pip)
                _sql_job_set_status(queue, "ce", jobid)
                _sql_job_set_time(queue, 'completed_at', jobid)

        # check existing jobs in queue
        conn = queue()
        cur = conn.cursor()
        cur.execute(
            "SELECT jobid, payload, status FROM queue;"
        )
        ret = cur.fetchall()
        conn.close()
        for jobid, strpl, st in ret:
            payload = json.loads(strpl)
            if st in ["q", "qw"]:
                log.debug(f"checking whether job '{jobid}' can be matched")
                matched_pips = _find_matching_pipelines(pipelines, payload["method"])
                if len(matched_pips) > 0:
                    log.debug(f"checking whether job '{jobid}' can be queued")
                    _sql_job_set_status(queue, "qw", jobid)
                for pip in matched_pips:
                    can_queue  = _pipeline_ready_sample(state, pip, payload["sample"])
                    if can_queue:
                        log.debug(f"queueing job '{jobid}'")
                        pid = os.fork()
                        if pid == 0:
                            driver_worker(settings, pip, payload)
                            if payload["tomato"]["unlock_when_done"]:
                                _sql_job_set_status(queue, "c", jobid)
                            else:
                                _sql_job_set_status(queue, "cw", jobid)
                            _sql_job_set_time(queue, "completed_at", jobid)
                            os._exit(0)
                        else:
                            _sql_pip_assign(state, pip, jobid, pid)
                            _sql_job_set_status(queue, "r", jobid)
                            _sql_job_set_time(queue, "executed_at", jobid)
                            break
        time.sleep(1)


        # - if jobid->status == q:
        #     find matching pipelines -> qw
        # - if jobid->status == qw:
        #     find matching pipelines
        #     find matching samples
        #     is pipeline ready -> r -> assign jobid and pid into pipeline state 

    #for pname, pvals in pipelines.items():
    #    print(f'driver_worker(settings, pvals, None): with {pname}')
    #    driver_worker(settings, pvals, None)
    
