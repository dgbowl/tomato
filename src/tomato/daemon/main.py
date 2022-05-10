import psutil
import os
import subprocess
import time
import json
import logging

from ..drivers import driver_worker, driver_reset, tomato_job
from .. import dbhandler


def _find_matching_pipelines(pipelines: list, method: list[dict]) -> list[str]:
    req_names = set([item["device"] for item in method])
    req_capabs = set([item["technique"] for item in method])

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
                    log.info(f"checking whether job '{jobid}' can ever be matched")
                matched_pips = _find_matching_pipelines(pipelines, payload["method"])
                if len(matched_pips) > 0 and st != "qw":
                    dbhandler.job_set_status(qup, "qw", jobid, type=qut)
                log.debug(f"checking whether job '{jobid}' can be queued")
                for pip in matched_pips:
                    pipinfo = dbhandler.pipeline_get_info(stp, pip["name"], type=stt)
                    can_queue = _pipeline_ready_sample(pipinfo, payload["sample"])
                    if can_queue:
                        log.info(f"queueing job '{jobid}' on pipeline '{pip['name']}'")
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
                        cfs = subprocess.CREATE_NO_WINDOW
                        #cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                        subprocess.Popen(
                            ["tomato_job", str(jpath)],
                            creationflags=cfs,
                        )
                        break
        time.sleep(settings.get("main loop", 1))
