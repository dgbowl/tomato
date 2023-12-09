"""
**tomato.daemon**: module of functions comprising the tomato daemon
-------------------------------------------------------------------
.. codeauthor:: 
    Peter Kraus
"""
import os
import subprocess
import logging
import time
import argparse
import json
import copy
from threading import Thread, currentThread
from datetime import datetime, timezone
from pathlib import Path
import toml

import zmq
import psutil

from tomato.models import Pipeline, Reply, Daemon, Job
from tomato import tomato
import tomato.daemon.cmd as cmd
import tomato.daemon.job as job

logger = logging.getLogger(__name__)


def setup_logging(daemon: Daemon):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(Path(daemon.logdir) / f"daemon_{daemon.port}.log")
    fh.setLevel(daemon.verbosity)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)8s - %(name)-30s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def run_daemon():
    """ """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", "-p", type=int, default=1234)
    parser.add_argument("--verbosity", "-V", type=int, default=logging.INFO)
    parser.add_argument("--appdir", "-A", type=Path, default=Path.cwd())
    parser.add_argument("--logdir", "-L", type=Path, default=Path.cwd())
    args = parser.parse_args()
    settings = toml.load(args.appdir / "settings.toml")

    daemon = Daemon(**vars(args), status="bootstrap", settings=settings)
    setup_logging(daemon)
    logger.info(f"logging set up with verbosity {daemon.verbosity}")

    context = zmq.Context()
    rep = context.socket(zmq.REP)
    logger.debug(f"binding zmq.REP socket on port {daemon.port}")
    rep.bind(f"tcp://127.0.0.1:{daemon.port}")
    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    logger.debug(f"entering main loop")
    jmgr = None
    while True:
        socks = dict(poller.poll(100))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug(f"received {msg=}")
            if "cmd" not in msg:
                logger.error(f"received msg without cmd: {msg=}")
                ret = Reply(success=False, msg="received msg without cmd", data=msg)
            elif msg["cmd"] == "status":
                ret = cmd.status(msg, daemon)
            elif msg["cmd"] == "stop":
                ret = cmd.stop(msg, daemon)
                if jmgr is not None:
                    jmgr.do_run = False
                    jmgr.join()
                    logger.info("job manager thread joined successfully")
            elif msg["cmd"] == "setup":
                settings = msg["settings"]
                ret = cmd.setup(msg, daemon)
                if jmgr is None:
                    jmgr = Thread(target=job.manager, args=(daemon.port, context))
                    jmgr.do_run = True
                    jmgr.start()
                    logger.info("job manager thread started")
            elif msg["cmd"] == "pipeline":
                ret = cmd.pipeline(msg, daemon)
            elif msg["cmd"] == "job":
                ret = cmd.job(msg, daemon)
            logger.debug(f"reply with {ret=}")
            rep.send_pyobj(ret)
        if daemon.status == "stop":
            break
