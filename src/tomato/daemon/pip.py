"""
**tomato.daemon.pip**: the pipeline manager of tomato daemon
------------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

import logging
import time
from datetime import datetime, timedelta
from datetime import timezone as tz
from threading import current_thread

import psutil
import zmq

from tomato.daemon import drvdb, jobdb, pipdb
from tomato.models import Daemon
from tomato.utils import context

MAX_JOB_NOPID = 10


def manager(timeout: int = 500):
    """
    The pipeline manager thread of `tomato-daemon`.

    This manager ensures the job queue is iterated over and pipelines are managed/reset. Note that we poll the `tomato-daemon` for status only once per iteration of the main loop.
    """
    logger = logging.getLogger(f"{__name__}.manager")
    thread = current_thread()
    logger.info("launched successfully")
    req: zmq.Socket = context.socket(zmq.REQ)
    # req.connect(f"tcp://127.0.0.1:{port}")
    req.connect("inproc://daemon")
    while getattr(thread, "do_run"):  # noqa: B009
        msg = {"cmd": "status", "sender": f"{__name__}.manager"}
        req.send_pyobj(msg)
        ret = req.recv_pyobj()
        if req.closed:
            break
        elif ret.success is False or ret.data is None:
            logger.critical("tomato-daemon is not running: %s", ret.msg)
            break
        daemon: Daemon = ret.data
        dbpath = daemon.settings["jobs"]["dbpath"]

        running = pipdb.get_pips_where("jobid IS NOT NULL", dbpath)
        for pip in running:
            job = jobdb.get_job_id(pip.jobid, dbpath)  # ty: ignore[invalid-argument-type]
            logger.debug("%s: checking pipeline with jobid %d", pip.name, job.id)
            if job.pid is None and job.connected_at is not None:
                # job.pid is reset to None when job is terminated
                pass
            elif job.pid is None and job.launched_at is not None:
                # subprocess was started but job is not (yet) connected
                td = datetime.now(tz.utc) - datetime.fromisoformat(job.launched_at)
                if td > timedelta(MAX_JOB_NOPID):
                    pass
                else:
                    continue
            elif job.pid is None or (
                psutil.pid_exists(job.pid)
                and psutil.Process(job.pid).status() is not psutil.STATUS_ZOMBIE
            ):
                continue

            logger.warning("%s: pipeline will be reset", pip.name)
            for cn in daemon.devicefile.pipelines[pip.name].components.values():
                cmp = daemon.devicefile.components[cn]
                drv = drvdb.get_drv(name=cmp.driver, dbpath=dbpath)
                assert drv is not None
                logger.warning("%s: resetting component '%s'", pip.name, cn)
                dreq = context.socket(zmq.REQ)
                dreq.connect(f"tcp://127.0.0.1:{drv.port}")
                params = cmp.model_dump()
                dreq.send_pyobj({"cmd": "cmp_reset", "params": params})
                dret = dreq.recv_pyobj()
                if dret.success is False:
                    logger.warning(
                        "%s: reset of component '%s' failed: %s", pip.name, cn, dret.msg
                    )
            logger.debug("%s: clearing pipeline jobid", pip.name)
            params = {"jobid": None, "ready": False}
            pipdb.update_pip(name=pip.name, params=params, dbpath=dbpath)
        time.sleep(timeout / 1e3)
    req.close()
    logger.info("instructed to quit")
