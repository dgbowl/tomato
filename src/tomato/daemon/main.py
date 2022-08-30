import psutil
import os
import subprocess
import time
import json
import logging
from .. import dbhandler

log = logging.getLogger(__name__)


def _kill_tomato_job(proc):
    pc = proc.children()
    log.warning(
        "killing proc: name='%s', pid=%d, children=%d", proc.name(), proc.pid, len(pc)
    )
    if psutil.WINDOWS:
        for proc in pc:
            if proc.name() in {"conhost.exe"}:
                continue
            ppc = proc.children()
            for proc in ppc:
                try:
                    proc.terminate()
                except psutil.NoSuchProcess:
                    log.warning(
                        "dead proc: name='%s', pid=%d", proc.name(), proc.pid
                    )
                    continue
            gone, alive = psutil.wait_procs(ppc, timeout=10)
    elif psutil.POSIX:
        for proc in pc:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                log.warning(
                    "dead proc: name='%s', pid=%d", proc.name(), proc.pid
                )
                continue
        gone, alive = psutil.wait_procs(pc, timeout=10)
    log.debug(f"{gone=}")
    log.debug(f"{alive=}")


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
    sampleid, ready, _, _ = ret
    if ready == 0:
        return False
    else:
        if sample["name"] == sampleid:
            return True
        else:
            return False


def main_loop(settings: dict, pipelines: dict, test: bool = False) -> None:
    log.info("Entered 'main_loop'.")
    qup = settings["queue"]["path"]
    qut = settings["queue"]["type"]
    stp = settings["state"]["path"]
    stt = settings["state"]["type"]
    while True:
        # check existing PIDs in state
        ret = dbhandler.pipeline_get_running(stp, type=stt)
        for pip, jobid, pid in ret:
            log.debug(f"checking PID of running job '{jobid}'")
            if psutil.pid_exists(pid) and "tomato_job" in psutil.Process(pid).name():
                log.debug(f"PID of running job '{jobid}' found")
                _, _, st, _, _, _ = dbhandler.job_get_info(qup, jobid, type=qut)
                if st in {"rd"}:
                    log.warning(f"cancelling a running job {jobid} with pid {pid}")
                    proc = psutil.Process(pid=pid)
                    log.debug(f"{proc=}")
                    _kill_tomato_job(proc)
                    log.info(f"setting job {jobid} to status 'cd'")
                    dbhandler.job_set_status(qup, "cd", jobid, type=qut)
            else:
                log.debug(f"PID of running job '{jobid}' not found")
                dbhandler.pipeline_reset_job(stp, pip, False, type=stt)
                dbhandler.job_set_status(qup, "ce", jobid, type=qut)
                dbhandler.job_set_time(qup, "completed_at", jobid, type=qut)

        # check queued jobs in queue, get their payloads and any matching pipelines
        ret = dbhandler.job_get_all_queued(qup, type=qut)
        matched_pips = {}
        payloads = {}
        jobids = []
        for jobid, _, strpl, st in ret:
            payload = json.loads(strpl)
            payloads[jobid] = payload
            jobids.append(jobid)
            if st == "q":
                log.info(f"checking whether job '{jobid}' can ever be matched")
            matched_pips[jobid] = _find_matching_pipelines(pipelines, payload["method"])
            if len(matched_pips[jobid]) > 0 and st != "qw":
                dbhandler.job_set_status(qup, "qw", jobid, type=qut)

        # iterate over sorted queued jobs and submit if pipeline with is loaded & ready
        for jobid in sorted(jobids):
            payload = payloads[jobid]
            log.debug(f"checking whether job '{jobid}' can be queued")
            for pip in matched_pips[jobid]:
                pipinfo = dbhandler.pipeline_get_info(stp, pip["name"], type=stt)
                if not _pipeline_ready_sample(pipinfo, payload["sample"]):
                    continue
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
                if psutil.WINDOWS:
                    cfs = subprocess.CREATE_NO_WINDOW
                    if not test:
                        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
                    subprocess.Popen(
                        ["tomato_job", str(jpath)],
                        creationflags=cfs,
                    )
                elif psutil.POSIX:
                    sns = False if test else True
                    subprocess.Popen(
                        ["tomato_job", str(jpath)],
                        start_new_session=sns,
                    )
                break
        time.sleep(settings.get("main loop", 1))
