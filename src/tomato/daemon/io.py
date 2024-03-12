"""
**tomato.daemon.io**: store and load state of tomato daemon
-----------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import pickle
import logging
import xarray as xr
from pathlib import Path
from tomato.models import Daemon

logger = logging.getLogger(__name__)


def store(daemon: Daemon):
    datadir = Path(daemon.settings["datadir"])
    datadir.mkdir(parents=True, exist_ok=True)
    outfile = datadir / f"tomato_state_{daemon.port}.pkl"
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


def merge_netcdfs(jobpath: Path, outpath: Path):
    logger = logging.getLogger(f"{__name__}.merge_netcdf")
    logger.debug("opening datasets")
    datasets = []
    for fn in jobpath.glob("*.pkl"):
        with pickle.load(fn.open("rb")) as ds:
            datasets.append(ds)
    logger.debug(f"merging {datasets=}")
    if len(datasets) > 0:
        ds = xr.concat(datasets, dim="uts")
        ds.to_netcdf(outpath, engine="h5netcdf")


def data_to_pickle(ds: xr.Dataset, path: Path):
    logger = logging.getLogger(f"{__name__}.data_to_pickle")
    logger.debug("checking existing")
    if path.exists():
        with pickle.load(path.open("rb")) as oldds:
            ds = xr.concat([oldds, ds], dim="uts")
    logger.debug("dumping pickle")
    with path.open("wb") as out:
        pickle.dump(ds, out, protocol=5)
