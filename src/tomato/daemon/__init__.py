"""
.. codeauthor::
    Peter Kraus

"""

import argparse
import logging
from pathlib import Path
from threading import Thread

import zmq

import tomato.daemon.driver
import tomato.daemon.job
import tomato.daemon.pip
from tomato.daemon import cmd
from tomato.models import Daemon, Reply
from tomato.utils import context

logger = logging.getLogger(__name__)


def setup_logging(daemon: Daemon):
    """
    Helper function to set up logging (folder, filename, verbosity, format) based on the passed daemon state.
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
    The function called when :obj:`tomato-daemon` is executed.

    Manages the state of the tomato daemon, spawning manager threads for jobs (:mod:`~tomato.daemon.job`), drivers (:mod:`~tomato.daemon.driver`), and pipelines (:mod:`~tomato.daemon.pip`). Parses the configuration in the :ref:`settings file <settings-file>` and :ref:`devices file <devices-file>`.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", "-p", type=int, default=1234)
    parser.add_argument("--verbosity", "-V", type=int, default=logging.INFO)
    parser.add_argument("--appdir", "-A", type=str, default=str(Path.cwd()))

    args = parser.parse_args()

    daemon = Daemon(**vars(args), status="bootstrap")
    setup_logging(daemon)
    logger.info("logging set up with verbosity %s", daemon.verbosity)

    cmd.reload(msg={}, daemon=daemon)
    rep = context.socket(zmq.REP)
    logger.debug("binding zmq.REP socket on port %d", daemon.port)
    rep.bind(f"tcp://127.0.0.1:{daemon.port}")
    rep.bind("inproc://daemon")
    poller = zmq.Poller()
    poller.register(rep, zmq.POLLIN)

    logger.debug("entering main loop")
    threads = {}
    managers = {"pip", "job", "driver"}
    while True:
        socks = dict(poller.poll(1000))
        if rep in socks:
            msg = rep.recv_pyobj()
            logger.debug("received msg: %s", msg)
            if "cmd" not in msg:
                logger.error("received msg without cmd: %s", msg)
                ret = Reply(success=False, msg="received msg without cmd", data=msg)
            elif hasattr(cmd, msg["cmd"]):
                ret = getattr(cmd, msg["cmd"])(msg, daemon)
            else:
                logger.error("received msg with an invalid cmd: %s", msg["cmd"])
            logger.debug("reply: %s", ret)
            rep.send_pyobj(ret)

        if daemon.status == "stop":
            end = True
            for mgr, thread in threads.items():
                if getattr(thread, "do_run"):  # noqa:B009
                    logger.debug("stopping %s manager thread", mgr)
                    setattr(thread, "do_run", False)  # noqa:B010
                if mgr is not None and thread.is_alive():
                    end = False
            if end:
                for mgr in threads.values():
                    assert mgr.is_alive() is False
                logger.info("all manager threads joined")
                break
        else:
            for mgr in managers:
                thread = threads.get(mgr)
                if thread is None or not thread.is_alive():
                    if thread is None:
                        logger.info("starting %s manager thread", mgr)
                    else:
                        logger.warning("restarting %s manager thread", mgr)
                    target = getattr(tomato.daemon, mgr).manager
                    threads[mgr] = Thread(target=target, daemon=True)
                    setattr(threads[mgr], "do_run", True)  # noqa: B010
                    threads[mgr].start()
    logger.critical("tomato-daemon on port %d is exiting", daemon.port)
