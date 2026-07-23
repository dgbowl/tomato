"""
**tomato.daemon**: module of functions comprising the tomato daemon
-------------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import argparse
import logging
from pathlib import Path
from threading import Thread

import zmq

import tomato.daemon.cmd as cmd
import tomato.daemon.driver
import tomato.daemon.job
import tomato.daemon.pip
from tomato.models import Daemon, Reply

logger = logging.getLogger(__name__)


def setup_logging(daemon: Daemon):
    """
    Helper function to set up logging (folder, filename, verbosity, format) based on
    the passed daemon state.
    """
    logdir = Path(daemon.settings["logdir"])
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"tomato_daemon_{daemon.port}.log"
    logging.basicConfig(
        level=daemon.verbosity,
        format="%(asctime)s - %(levelname)8s - %(name)-35s - %(message)s",
        handlers=[logging.FileHandler(logfile, mode="a")],
    )


def tomato_daemon():
    """
    The function called when `tomato-daemon` is executed.

    Manages the state of the tomato daemon, including recovery of state via
    :mod:`~tomato.daemon.io`, processing state updates via :mod:`~tomato.daemon.cmd`,
    and the manager threads for both jobs (:mod:`~tomato.daemon.job`) and drivers
    (:mod:`~tomato.daemon.driver`).
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", "-p", type=int, default=1234)
    parser.add_argument("--verbosity", "-V", type=int, default=logging.INFO)
    parser.add_argument("--appdir", "-A", type=str, default=str(Path.cwd()))

    args = parser.parse_args()

    daemon = Daemon(**vars(args), status="bootstrap")
    setup_logging(daemon)
    logger.info("logging set up with verbosity %s", daemon.verbosity)

    # TODO: setup should not be a thing really.
    cmd.setup(msg={}, daemon=daemon)
    context = zmq.Context()
    rep = context.socket(zmq.REP)
    logger.debug("binding zmq.REP socket on port %d", daemon.port)
    rep.bind(f"tcp://127.0.0.1:{daemon.port}")
    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    logger.debug("entering main loop")
    pmgr = Thread(target=tomato.daemon.pip.manager, args=(daemon.port,), daemon=True)
    setattr(pmgr, "do_run", True)
    pmgr.start()
    jmgr = Thread(target=tomato.daemon.job.manager, args=(daemon.port,), daemon=True)
    setattr(jmgr, "do_run", True)
    jmgr.start()
    dmgr = Thread(target=tomato.daemon.driver.manager, args=(daemon.port,), daemon=True)
    setattr(dmgr, "do_run", True)
    dmgr.start()
    while True:
        socks = dict(poller.poll(1000))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug(f"received {msg=}")
            if "cmd" not in msg:
                logger.error(f"received msg without cmd: {msg=}")
                ret = Reply(success=False, msg="received msg without cmd", data=msg)
            elif hasattr(cmd, msg["cmd"]):
                ret = getattr(cmd, msg["cmd"])(msg, daemon)
            else:
                logger.error(f"received msg with an invalid cmd: {msg=}")
            logger.debug(f"reply with {ret=}")
            rep.send_pyobj(ret)
        if daemon.status == "stop":
            end = True
            for mgr, label in [(jmgr, "job"), (dmgr, "driver"), (pmgr, "pip")]:
                if getattr(mgr, "do_run"):
                    logger.debug("stopping %s manager thread", label)
                    setattr(mgr, "do_run", False)
                if mgr.is_alive():
                    end = False
            if end:
                assert dmgr.is_alive() is False
                assert jmgr.is_alive() is False
                assert pmgr.is_alive() is False
                logger.info("all manager threads joined")
                break
    logger.critical("tomato-daemon on port %d is exiting", daemon.port)
