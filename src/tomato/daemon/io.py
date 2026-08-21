"""
**tomato.daemon.io**: functions for storing job data
----------------------------------------------------
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
    Merges all of the individual pickled :class:`~xarray.Dataset` files from each component found in :obj:`job.jobpath` into a single :class:`~xarray.DataTree`, which is then stored in the NetCDF file. The role of each component is used as the group label.
    """
    logger = logging.getLogger(f"{__name__}.merge_netcdf")
    assert job.jobpath is not None
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
    outstr = job.snappath if snapshot else job.respath
    assert outstr is not None
    outpath = Path(outstr).resolve()
    logger.debug("saving DataTree into a NetCDF file at '%s'", outpath)
    with outpath.open("w+b") as out:
        dt.to_netcdf(out, engine="h5netcdf")
        dt.close()
    return str(outpath)


def data_to_pickle(ds: xr.Dataset, path: Path, role: str):
    """
    Dumps the data provided as :class:`~xarray.Dataset` using :mod:`pickle`. Concatenates the new data with any existing data stored in the existing ``.pkl`` file.
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
