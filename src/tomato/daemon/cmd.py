from tomato.models import Daemon, Driver, Device, Reply, Pipeline, Job
from copy import deepcopy
from threading import Thread
import logging
import tomato.daemon.job, tomato.daemon.driver

logger = logging.getLogger(__name__)


def merge_pipelines(
    cur: dict[str, Pipeline], new: dict[str, Pipeline]
) -> dict[str, Pipeline]:
    ret = {}
    for pname, pip in cur.items():
        if pname not in new:
            if pip.jobid is not None:
                ret[pname] = pip
        else:
            if pip.devs == new[pname].devs:
                ret[pname] = pip
            elif pip.jobid is None:
                ret[pname] = new[pname]
    for pname, pip in new.items():
        if pname not in cur:
            ret[pname] = pip
    return ret


def status(msg: dict, daemon: Daemon) -> Reply:
    if msg.get("with_data", False):
        return Reply(success=True, msg=daemon.status, data=deepcopy(daemon))
    else:
        return Reply(success=True, msg=daemon.status)


def stop(msg: dict, daemon: Daemon, jmgr: Thread = None, dmgr: Thread = None) -> Reply:
    daemon.status = "stop"
    logger.critical("stopping daemon")
    for mgr, label in [(jmgr, "job"), (dmgr, "driver")]:
        if mgr is not None:
            logger.debug(f"stopping {label} manager thread")
            mgr.do_run = False
    return Reply(success=True, msg=daemon.status)


def setup(msg: dict, daemon: Daemon, jmgr: Thread = None, dmgr: Thread = None) -> Reply:
    for key in ["drvs", "devs", "pips"]:
        if key in msg:
            setattr(daemon, key, msg[key])
    if daemon.status == "bootstrap":
        if jmgr is None:
            jmgr = Thread(target=tomato.daemon.job.manager, args=(daemon.port,))
            jmgr.do_run = True
            jmgr.start()
        if dmgr is None:
            dmgr = Thread(target=tomato.daemon.driver.manager, args=(daemon.port,))
            dmgr.do_run = True
            dmgr.start()
        logger.info(f"setup successful with pipelines: {list(daemon.pips.keys())}")
        daemon.status = "running"
    else:
        logger.info(f"reload successful with pipelines: {list(daemon.pips.keys())}")
    return Reply(success=True, msg=daemon.status, data=daemon), jmgr, dmgr


def pipeline(msg: dict, daemon: Daemon) -> Reply:
    pname = msg.get("pipeline")
    for k, v in msg.get("params", {}).items():
        logger.info(f"setting pipeline {pname}.{k} to {v}")
        setattr(daemon.pips[pname], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.pips[pname])


def job(msg: dict, daemon: Daemon) -> Reply:
    jobid = msg.get("id", None)
    if jobid is None:
        jobid = daemon.nextjob
        daemon.jobs[jobid] = Job(id=jobid, **msg.get("params", {}))
        daemon.nextjob += 1
    else:
        for k, v in msg.get("params", {}).items():
            logger.debug(f"setting job {jobid}.{k} to {v}")
            setattr(daemon.jobs[jobid], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.jobs[jobid])


def driver(msg: dict, daemon: Daemon) -> Reply:
    drv = msg["params"]
    if drv["name"] is None:
        logger.error()
        return Reply(success=False, msg="no driver name supplied", data=msg)
    if drv["name"] not in daemon.drvs:
        daemon.drvs[drv["name"]] = Driver(**drv)
    else:
        for k, v in drv.items():
            logger.debug(f"setting driver '{drv['name']}.{k}' to {v}")
            setattr(daemon.drvs[drv["name"]], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.drvs[drv["name"]])


def device(msg: dict, daemon: Daemon) -> Reply:
    dev = msg["params"]
    if dev["name"] is None:
        logger.error()
        return Reply(success=False, msg="no device name supplied", data=msg)
    if dev["name"] not in daemon.devs:
        daemon.devs[dev["name"]] = Device(**dev)
    else:
        for k, v in dev.items():
            logger.debug(f"setting device '{dev['name']}.{k}' to {v}")
            setattr(daemon.devs[dev["name"]], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.devs[dev["name"]])
