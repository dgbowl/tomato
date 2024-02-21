from tomato.models import Daemon, Driver, Reply, Pipeline, Job
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
    logger.critical(f"{ret=}")
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
    daemon.devs = msg["devs"]
    daemon.pips = merge_pipelines(daemon.pips, msg["pips"])
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
        logger.critical(f"{daemon.pips=}")
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
            logger.info(f"setting job {jobid}.{k} to {v}")
            setattr(daemon.jobs[jobid], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.jobs[jobid])


def driver(msg: dict, daemon: Daemon) -> Reply:
    name = msg.get("name", None)
    if name is None:
        logger.error()
        return Reply(success=False, msg=msg)
    if name not in daemon.drvs:
        daemon.drvs[name] = Driver(name=name, **msg.get("params", {}))
    else:
        for k, v in msg.get("params", {}).items():
            if v is None or v == getattr(daemon.drvs[name], k):
                continue
            logger.info(f"setting driver {name}.{k} to {v}")

            setattr(daemon.drvs[name], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.drvs[name])
