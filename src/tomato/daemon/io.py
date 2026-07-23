"""
**tomato.daemon.io**: functions for storing and loading data
------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import importlib.metadata
import logging
import pickle
from pathlib import Path

import xarray as xr

from tomato.models import Job

logger = logging.getLogger(__name__)


def merge_netcdfs(job: Job, snapshot=False) -> str:
    """
    Merges the individual pickled :class:`xr.Datasets` of each Component found in :obj:`job.jobpath`
    into a single :class:`xr.DataTree`, which is then stored in the NetCDF file,
    using the Component `role` as the group label.
    """
    logger = logging.getLogger(f"{__name__}.merge_netcdf")
    logger.debug("opening datasets in '%s'", job.jobpath)
    datasets = []
    for fn in Path(job.jobpath).glob("*.pkl"):
        with fn.open("rb") as pkl:
            ds = pickle.load(pkl)
            if ds is not None:
                datasets.append(ds)
    logger.debug("creating a DataTree from %d groups", len(datasets))
    dt = xr.DataTree.from_dict({ds.attrs["role"]: ds for ds in datasets})
    logger.debug(f"{dt=}")
    root_attrs = {
        "tomato_version": importlib.metadata.version("tomato"),
        "tomato_Job": job.model_dump_json(),
    }
    dt.attrs = root_attrs
    outpath = Path(job.snappath if snapshot else job.respath).resolve()
    logger.debug("saving DataTree into a NetCDF file at '%s'", outpath)
    dt.to_netcdf(outpath, engine="h5netcdf")
    dt.close()
    return str(outpath)


def data_to_pickle(ds: xr.Dataset, path: Path, role: str):
    """
    Dumps the data provided as :class:`xr.Dataset` into a ``pickle``. Concatenates with
    any existing data stored in the ``pickle``.
    """
    logger = logging.getLogger(f"{__name__}.data_to_pickle")
    ds.attrs["role"] = role
    logger.debug("checking for existing pickle at '%s'", path)
    if path.exists():
        with path.open("rb") as old:
            oldds = pickle.load(old)
        if oldds is not None:
            logger.debug("concatenating Dataset with existing data")
            ds = xr.concat([oldds, ds], dim="uts")
    logger.debug("dumping Dataset into pickle at '%s'", path)
    with path.open("wb") as out:
        pickle.dump(ds, out, protocol=4)
