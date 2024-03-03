"""
**tomato.daemon.io**: store and load state of tomato daemon
-----------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""
import pickle
import logging
from pathlib import Path
from tomato.models import Daemon

logger = logging.getLogger(__name__)


def store(daemon: Daemon):
    outfile = Path(daemon.settings["datadir"]) / f"tomato_state_{daemon.port}.pkl"
    logger.debug(f"storing daemon state to {outfile}")
    with outfile.open("wb") as out:
        pickle.dump(daemon, out, protocol=5)


def load(daemon: Daemon):
    infile = Path(daemon.settings["datadir"]) / f"tomato_state_{daemon.port}.pkl"
    if infile.exists() is False:
        logger.debug(f"daemon state file {infile} does not exist")
        return
    with infile.open("rb") as inp:
        loaded = pickle.load(inp)
    daemon.jobs = loaded.jobs
    daemon.pips = loaded.pips
    daemon.devs = loaded.devs
    daemon.drvs = loaded.drvs
    daemon.nextjob = loaded.nextjob
    daemon.status = "running"
