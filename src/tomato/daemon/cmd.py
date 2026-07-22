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

import logging
import tomato.daemon.io as io
import tomato.daemon.jobdb as jobdb
import tomato.utils
from pathlib import Path
from pydantic import BaseModel
from tomato.models import (
    Component,
    Daemon,
    Device,
    Job,
    Pipeline,
    Reply,
    SpawnData,
)
from typing import Any

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
            if pip.components == new[pname].components:
                ret[pname] = pip
            elif pip.jobid is None:
                ret[pname] = new[pname]
    for pname, pip in new.items():
        if pname not in cur:
            ret[pname] = pip
    return ret


def status(msg: dict, daemon: Daemon) -> Reply:
    return Reply(success=True, msg=daemon.status, data=daemon)


def stop(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.stop")
    logger.debug("%s", msg)
    io.store(daemon)
    if any([pip.jobid is not None for pip in daemon.pips.values()]):
        running = {pip.jobid for pip in daemon.pips.values() if pip.jobid is not None}
        logger.error("cannot stop tomato-daemon as jobs are running: %s", running)
        return Reply(success=False, msg=f"jobs are running: {running}")
    else:
        daemon.status = "stop"
        logger.critical("stopping tomato-daemon")
        return Reply(success=True)


def setup(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.setup")

    # TODO: Rework this!
    devicefile = tomato.utils.load_device_file(
        Path(daemon.settings["devices"]["config"]),
        logger,
    )
    logger.debug(f"{devicefile=}")
    devs = {dev["name"]: Device(**dev) for dev in devicefile["devices"]}
    logger.debug(f"{devs=}")
    pips, cmps = tomato.utils.get_pipelines(
        devs,
        devicefile["pipelines"],
        logger,
    )
    logger.debug(f"{pips=}")
    logger.debug(f"{cmps=}")

    if daemon.status == "bootstrap":
        for key, val in [
            # ("drvs", drvs),
            # ("devs", devs),
            ("pips", pips),
            ("cmps", cmps),
        ]:
            setattr(daemon, key, val)

        daemon.drivers = {
            key: SpawnData(name=key) for key in daemon.devicefile.drivers.keys()
        }
        logger.info("setup successful with pipelines: '%s'", daemon.pips.keys())
        daemon.status = "running"
    else:
        try:
            nd = Daemon(
                status=daemon.status,
                port=daemon.port,
                appdir=daemon.appdir,
                verbosity=daemon.verbosity,
            )
        except Exception as e:
            logger.critical("Error", exc_info=e)
            return Reply(
                success=False,
                msg="could not parse updated settings",
            )
        logger.debug(f"{nd=}")
        ndf = nd.devicefile
        # First, check that we're not touching anything associated with a running job
        check_components = set()
        check_devices = set()
        check_drivers = set()
        for dpip in daemon.pips.values():
            logger.debug(f"{dpip=}")
            if dpip.jobid is None:
                continue
            if dpip.name not in pips:
                return Reply(
                    success=False,
                    msg="reload would delete a running pipeline",
                    data=dpip,
                )
            pip = pips[dpip.name]
            if pip.components != dpip.components:
                return Reply(
                    success=False,
                    msg="reload would modify components of a running pipeline",
                    data=dpip,
                )
            check_components.update(dpip.components)

        for cname in check_components:
            dcomp = daemon.cmps[cname]
            if cname not in cmps:
                return Reply(
                    success=False,
                    msg="reload would delete a component of a running pipeline",
                    data=dcomp,
                )
            comp = cmps[cname]
            if (
                dcomp.name != comp.name
                or dcomp.driver != comp.driver
                or dcomp.device != comp.device
                or dcomp.address != comp.address
                or dcomp.channel != comp.channel
                or dcomp.role != comp.role
            ):
                return Reply(
                    success=False,
                    msg="reload would modify a component of a running pipeline",
                    data=dcomp,
                )
            check_devices.add(dcomp.device)
            check_drivers.add(dcomp.driver)

        for dname in check_drivers:
            if dname not in ndf.drivers:
                return Reply(
                    success=False,
                    msg="reload would delete a driver of a device in a running pipeline",
                    data=daemon.drivers[dname],
                )

            if daemon.devicefile.drivers[dname].settings != ndf.drivers[dname].settings:
                return Reply(
                    success=False,
                    msg="reload would modify a driver of a device in a running pipeline",
                    data=daemon.devicefile.drivers[dname].settings,
                )

        logger.critical("goint into api reload")

        _api_reload(pips, daemon.pips, "pipeline", ["components"])
        attrlist = ["driver", "device", "address", "channel", "role"]
        _api_reload(cmps, daemon.cmps, "component", attrlist)
        # Add new drivers, they will be spawned by driver.manager
        for dname in ndf.drivers.keys():
            if dname not in daemon.drivers:
                logger.info("adding new driver '%s'", dname)
                daemon.drivers[dname] = SpawnData(name=dname)

        # We want to trigger re-parse of config files on daemon
        daemon.settings = nd.settings
        daemon.devicefile = ndf
        logger.info("reload successful with pipelines: '%s'", daemon.pips.keys())

    return Reply(success=True, data=daemon)


def _api_reload(mdict: dict, ddict: dict, objname: str, attrlist: list[str]):
    for obj in mdict.values():
        if obj.name not in ddict:
            logger.debug("adding new %s '%s'", objname, obj.name)
            ddict[obj.name] = obj
            continue
        dobj = ddict[obj.name]
        for attr in attrlist:
            if getattr(dobj, attr) != getattr(obj, attr):
                logger.debug("%s '%s.%s' updated", objname, dobj.name, attr)
                setattr(dobj, attr, getattr(obj, attr))
    for dobj in ddict.copy().values():
        if dobj.name not in mdict:
            logger.warning("removing unused %s '%s'", objname, dobj.name)
            del ddict[dobj.name]


def pipeline(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.pipeline")
    logger.debug("%s", msg)
    pip = msg["params"]
    if pip["name"] is None:
        logger.error("no pipeline name supplied")
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


def set_job(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.set_job")
    dbpath = daemon.settings["jobs"]["dbpath"]
    if msg["id"] is None:
        job = Job(**msg.get("params", {}))
        job.id = jobdb.insert_job(job, dbpath)
        logger.info("received job.id %d", job.id)
    else:
        job = jobdb.update_job_id(msg["id"], msg.get("params", {}), dbpath)
        logger.info("updated job.id %d", job.id)
    return Reply(success=True, msg="job updated", data=job)


def get_jobs(msg: dict, daemon: Daemon) -> Reply:
    dbpath = daemon.settings["jobs"]["dbpath"]
    jobs = jobdb.get_jobs_where(msg["where"], dbpath)
    return Reply(success=True, msg=f"found {len(jobs)} jobs", data=jobs)


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


def reload(msg: dict, daemon: Daemon, **kwargs: dict) -> Reply:
    # daemon.settings = toml.load(Path(daemon.appdir) / "settings.toml")
    return Reply(success=True, msg="daemon settings reloaded", data=daemon.settings)


def driver_set(msg: dict, daemon: Daemon) -> Reply:
    params = msg.pop("params")
    name = params.pop("name")
    for k, v in params.items():
        setattr(daemon.drivers[name], k, v)
    return Reply(success=True, msg=f"updated driver {name}", data=daemon.drivers[name])


def driver_del(msg: dict, daemon: Daemon) -> Reply:
    name = msg.pop("params").pop("name")
    del daemon.drivers[name]
    return Reply(success=True, msg=f"removed driver {name}")
