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

from tomato.models import Daemon, Driver, Device, Reply, Pipeline, Job, Component
from pydantic import BaseModel
from typing import Any
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
        return Reply(success=True, msg=daemon.status, data=daemon)
    else:
        return Reply(success=True, msg=daemon.status)


def stop(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.stop")
    logger.debug("%s", msg)
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
    logger.debug("%s", msg)
    if daemon.status == "bootstrap":
        for key in ["drvs", "devs", "pips", "cmps"]:
            if key in msg:
                setattr(daemon, key, msg[key])
        logger.info("setup successful with pipelines: '%s'", daemon.pips.keys())
        daemon.status = "running"
    else:
        logger.info("reload successful with pipelines: '%s'", daemon.pips.keys())
    return Reply(success=True, msg=daemon.status, data=daemon)


def pipeline(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.pipeline")
    logger.debug("%s", msg)
    pip = msg["params"]
    if pip["name"] is None:
        logger.error()
        return Reply(success=False, msg="no pipeline name supplied", data=msg)
    if pip["name"] not in daemon.pips:
        dest = Pipeline(**pip)
        daemon.pips[pip["name"]] = dest
        return Reply(success=True, msg="pipeline created", data=dest)

    dest = daemon.pips[pip["name"]]
    if pip.get("delete", False) and dest.jobid is None:
        logger.warning("deleting pipeline '%s'", dest.name)
        del daemon.pips[pip["name"]]
        return Reply(success=True, msg="pipeline deleted")

    elif pip.get("delete", False):
        logger.error("cannot delete pipeline '%s' as a job is running", dest.name)
        return Reply(success=False, msg="pipeline cannot be deleted", data=dest)
    else:
        for k, v in pip.items():
            logger.debug("setting pipeline '%s.%s' to '%s'", dest.name, k, v)
            setattr(dest, k, v)
        return Reply(success=True, msg="pipeline updated", data=dest)


def job(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.job")
    logger.debug("%s", msg)
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
    return Reply(success=True, msg="job updated", data=daemon.jobs[jobid])


def driver(msg: dict, daemon: Daemon) -> Reply:
    return _api(
        otype="driver",
        msg=msg,
        ddict=daemon.drvs,
        Cls=Driver,
    )


def device(msg: dict, daemon: Daemon) -> Reply:
    return _api(
        otype="device",
        msg=msg,
        ddict=daemon.devs,
        Cls=Device,
    )


def component(msg: dict, daemon: Daemon) -> Reply:
    return _api(
        otype="component",
        msg=msg,
        ddict=daemon.cmps,
        Cls=Component,
    )


def _api(otype: str, msg: dict, ddict: dict[str, Any], Cls: BaseModel) -> Reply:
    logger = logging.getLogger(f"{__name__}.{otype}")
    logger.debug("%s", msg)
    obj = msg["params"]
    if obj["name"] is None:
        logger.error("no %s name supplied", otype)
        return Reply(success=False, msg=f"no {otype} name supplied", data=msg)

    if obj["name"] not in ddict:
        ddict[obj["name"]] = Cls(**obj)
        return Reply(
            success=True,
            msg=f"{otype} {obj['name']!r} created",
            data=ddict[obj["name"]],
        )
    else:
        for k, v in obj.items():
            logger.debug("setting %s '%s.%s' to '%s'", otype, obj["name"], k, v)
            setattr(ddict[obj["name"]], k, v)
        return Reply(
            success=True,
            msg=f"{otype} {obj['name']!r} updated",
            data=ddict[obj["name"]],
        )
