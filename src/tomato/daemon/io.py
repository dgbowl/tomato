"""
**tomato.daemon.io**: functions for storing and loading data
------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import pickle
import logging
import xarray as xr
import importlib.metadata
from pathlib import Path
from tomato.models import Daemon, Job

logger = logging.getLogger(__name__)


def store(daemon: Daemon):
    """Stores the status of the provided :class:`Daemon` as a ``pickle`` file."""
    datadir = Path(daemon.settings["datadir"])
    datadir.mkdir(parents=True, exist_ok=True)
    outfile = datadir / f"tomato_state_{daemon.port}.pkl"
    logger.debug("storing daemon state to '%s'", outfile)
    with outfile.open("wb") as out:
        pickle.dump(daemon, out, protocol=5)


def load(daemon: Daemon):
    """Restores a saved status from a ``pickle`` file into the provided :class:`Daemon`."""
    infile = Path(daemon.settings["datadir"]) / f"tomato_state_{daemon.port}.pkl"
    if infile.exists() is False:
        logger.debug("daemon state file '%s' does not exist", infile)
        return
    with infile.open("rb") as inp:
        loaded = pickle.load(inp)
    daemon.pips = loaded.pips
    daemon.devs = loaded.devs
    daemon.drvs = loaded.drvs
    daemon.cmps = loaded.cmps
    daemon.status = "running"


def merge_netcdfs(job: Job, snapshot=False):
    """
    Merges the individual pickled :class:`xr.Datasets` of each Component found in :obj:`job.jobpath`
    into a single :class:`xr.DataTree`, which is then stored in the NetCDF file,
    using the Component `role` as the group label.
    """
    logger = logging.getLogger(f"{__name__}.merge_netcdf")
    logger.debug("opening datasets")
    datasets = []
    logger.debug(f"{job=}")
    logger.debug(f"{job.jobpath=}")
    for fn in Path(job.jobpath).glob("*.pkl"):
        with pickle.load(fn.open("rb")) as ds:
            datasets.append(ds)
    logger.debug("creating a DataTree from %d groups", len(datasets))
    dt = xr.DataTree.from_dict({ds.attrs["role"]: ds for ds in datasets})
    logger.debug(f"{dt=}")
    root_attrs = {
        "tomato_version": importlib.metadata.version("tomato"),
        "tomato_Job": job.model_dump_json(),
    }
    dt.attrs = root_attrs
    outpath = job.snappath if snapshot else job.respath
    logger.debug("saving DataTree into '%s'", outpath)
    dt.to_netcdf(outpath, engine="h5netcdf")
    logger.debug(f"{dt=}")


def data_to_pickle(ds: xr.Dataset, path: Path, role: str):
    """
    Dumps the data provided as :class:`xr.Dataset` into a ``pickle``. Concatenates with
    any existing data stored in the ``pickle``.
    """
    logger = logging.getLogger(f"{__name__}.data_to_pickle")
    ds.attrs["role"] = role
    logger.debug("checking for existing pickle at '%s'", path)
    if path.exists():
        with pickle.load(path.open("rb")) as oldds:
            logger.debug("concatenating Dataset with existing data")
            ds = xr.concat([oldds, ds], dim="uts")
    logger.debug("dumping Dataset into pickle at '%s'", path)
    with path.open("wb") as out:
        pickle.dump(ds, out, protocol=5)
