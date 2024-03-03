"""
**tomato.daemon.cmd**: command parsing for tomato daemon
--------------------------------------------------------
.. codeauthor::
    Peter Kraus

All functions in this module expect a :class:`dict` containing the command specification
and a :class:`~tomato.models.Daemon` object as arguments. The :class:`Daemon` object is
altered by the command.

All functions in this module return a :class:`~tomato.models.Reply`.

"""

from tomato.models import Daemon, Driver, Device, Reply, Pipeline, Job
from copy import deepcopy
import logging

import tomato.daemon.io as io

logger = logging.getLogger(__name__)


def merge_pipelines(
    cur: dict[str, Pipeline], new: dict[str, Pipeline]
) -> dict[str, Pipeline]:
    """
    Helper function for merging a :class:`dict` of new :class:`Pipelines` into the
    current :class:`dict`.
    """
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


def stop(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.stop")
    io.store(daemon)
    if any([pip.jobid is not None for pip in daemon.pips.values()]):
        logger.error("cannot stop tomato-daemon as jobs are running")
        return Reply(success=False, msg=daemon.status, data=daemon)
    else:
        daemon.status = "stop"
        logger.critical("stopping tomato-daemon")
        return Reply(success=True, msg=daemon.status)


def setup(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.setup")
    if daemon.status == "bootstrap":
        for key in ["drvs", "devs", "pips"]:
            if key in msg:
                setattr(daemon, key, msg[key])
        logger.info(f"setup successful with pipelines: {list(daemon.pips.keys())}")
        daemon.status = "running"
    else:
        logger.info(f"reload successful with pipelines: {list(daemon.pips.keys())}")
    return Reply(success=True, msg=daemon.status, data=daemon)


def pipeline(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.pipeline")
    pip = msg["params"]
    if pip["name"] is None:
        logger.error()
        return Reply(success=False, msg="no pipeline name supplied", data=msg)
    if pip["name"] not in daemon.pips:
        daemon.pips[pip["name"]] = Pipeline(**pip)
    elif pip.get("delete", False) and daemon.pips[pip["name"]].jobid is None:
        logger.warning(f"deleting pipeline {pip['name']!r}")
        del daemon.pips[pip["name"]]
    elif pip.get("delete", False):
        logger.error(f"cannot delete pipeline {pip['name']!r} as a job is running")
        return Reply(success=False, msg=daemon.status, data=daemon.pips[pip["name"]])
    else:
        for k, v in pip.items():
            logger.debug(f"setting pipeline '{pip['name']}.{k}' to {v}")
            setattr(daemon.pips[pip["name"]], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.pips.get(pip["name"]))


def job(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.job")
    jobid = msg.get("id", None)
    if jobid is None:
        jobid = daemon.nextjob
        daemon.jobs[jobid] = Job(id=jobid, **msg.get("params", {}))
        logger.info(f"received job {jobid}")
        daemon.nextjob += 1
    else:
        for k, v in msg.get("params", {}).items():
            logger.debug(f"setting job {jobid}.{k} to {v}")
            setattr(daemon.jobs[jobid], k, v)
    return Reply(success=True, msg=daemon.status, data=daemon.jobs[jobid])


def driver(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.driver")
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
    logger = logging.getLogger(f"{__name__}.device")
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
