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
    daemon.cmps = loaded.cmps
    daemon.nextjob = loaded.nextjob
    daemon.status = "running"


def merge_netcdfs(jobpath: Path, outpath: Path):
    """
    Merges the individual pickled :class:`xr.Datasets` of each Component found in
    `jobpath` into a single :class:`xr.DataTree`, which is then stored in the NetCDF file,
    using the Component `role` as the group label.
    """
    logger = logging.getLogger(f"{__name__}.merge_netcdf")
    logger.debug("opening datasets")
    datasets = []
    for fn in jobpath.glob("*.pkl"):
        with pickle.load(fn.open("rb")) as ds:
            datasets.append(ds)
    logger.debug(f"saving {len(datasets)} as groups")
    dt = xr.DataTree.from_dict({ds.attrs["role"]: ds for ds in datasets})
    dt.to_netcdf(outpath, engine="h5netcdf")


def data_to_pickle(ds: xr.Dataset, path: Path, role: str):
    """
    Dump the returned data into a pickle.

    Concatenates with existing data from the same Component.
    """
    logger = logging.getLogger(f"{__name__}.data_to_pickle")
    ds.attrs["role"] = role
    logger.debug("checking existing")
    if path.exists():
        with pickle.load(path.open("rb")) as oldds:
            ds = xr.concat([oldds, ds], dim="uts")
    logger.debug("dumping pickle")
    with path.open("wb") as out:
        pickle.dump(ds, out, protocol=5)
