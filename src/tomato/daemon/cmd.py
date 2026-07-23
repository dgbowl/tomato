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

import tomato.daemon.drvdb as drvdb
import tomato.daemon.pipdb as pipdb
from tomato.models import (
    Daemon,
    DrvState,
    PipState,
    Reply,
)

logger = logging.getLogger(__name__)


def status(msg: dict, daemon: Daemon) -> Reply:
    return Reply(success=True, msg=daemon.status, data=daemon)


def stop(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.stop")
    logger.debug("%s", msg)
    dbpath = daemon.settings["jobs"]["dbpath"]
    rpips = pipdb.get_pips_where("jobid IS NOT NULL", dbpath)
    if len(rpips) > 0:
        logger.error("cannot stop tomato-daemon as jobs are running: %s", rpips)
        return Reply(success=False, msg=f"{len(rpips)} jobs are running", data=rpips)
    else:
        daemon.status = "stop"
        logger.critical("stopping tomato-daemon")
        return Reply(success=True, msg="daemon set to stop")


def setup(msg: dict, daemon: Daemon) -> Reply:
    logger = logging.getLogger(f"{__name__}.setup")

    if daemon.status == "bootstrap":
        dbpath = daemon.settings["jobs"]["dbpath"]
        drvs = []
        for dname in daemon.devicefile.drivers.keys():
            ds = DrvState(name=dname)
            drv = drvdb.get_drv(name=dname, dbpath=dbpath)
            if drv is None:
                drv = drvdb.insert_drv(drv=ds, dbpath=dbpath)
            assert drv is not None
            drvs.append(drv.name)

        pips = []
        for pname in daemon.devicefile.pipelines.keys():
            ps = PipState(name=pname)
            pip = pipdb.get_pip(name=pname, dbpath=dbpath)
            if pip is None:
                pip = pipdb.insert_pip(pip=ps, dbpath=dbpath)
            assert pip is not None
            pips.append(pip.name)
        logger.info("setup successful with pipelines: %s and drivers: %s", pips, drvs)
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
        check_drivers = set()
        dbpath = daemon.settings["jobs"]["dbpath"]
        rpips = pipdb.get_pips_where("jobid IS NOT NULL", dbpath)
        for ps in rpips:
            dpip = daemon.devicefile.pipelines[ps.name]
            if dpip.name not in ndf.pipelines:
                return Reply(
                    success=False,
                    msg="reload would delete a running pipeline",
                    data=dpip,
                )
            pip = ndf.pipelines[dpip.name]
            if pip.components != dpip.components:
                return Reply(
                    success=False,
                    msg="reload would modify components of a running pipeline",
                    data=dpip,
                )
            check_components.update(dpip.components.values())

        for cname in check_components:
            dcomp = daemon.devicefile.components[cname]
            if cname not in ndf.components:
                return Reply(
                    success=False,
                    msg="reload would delete a component of a running pipeline",
                    data=dcomp,
                )
            comp = ndf.components[cname]
            if (
                dcomp.name != comp.name
                or dcomp.driver != comp.driver
                or dcomp.address != comp.address
                or dcomp.channel != comp.channel
            ):
                return Reply(
                    success=False,
                    msg="reload would modify a component of a running pipeline",
                    data=dcomp,
                )
            check_drivers.add(dcomp.driver)

        for dname in check_drivers:
            if dname not in ndf.drivers:
                return Reply(
                    success=False,
                    msg="reload would delete a driver of a device in a running pipeline",
                    data=daemon.devicefile.drivers[dname],
                )

            if daemon.devicefile.drivers[dname].settings != ndf.drivers[dname].settings:
                return Reply(
                    success=False,
                    msg="reload would modify a driver of a device in a running pipeline",
                    data=daemon.devicefile.drivers[dname].settings,
                )

        # We want to trigger re-parse of config files on daemon
        daemon.settings = nd.settings
        daemon.devicefile = ndf
        logger.info("reload successful with pipelines: '%s'", ndf.pipelines.keys())

    return Reply(success=True, msg="setup successful", data=daemon)


def reload(msg: dict, daemon: Daemon, **kwargs: dict) -> Reply:
    # daemon.settings = toml.load(Path(daemon.appdir) / "settings.toml")
    return Reply(success=True, msg="daemon settings reloaded", data=daemon.settings)
