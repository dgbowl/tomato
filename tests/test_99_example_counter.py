import pytest
import os
import subprocess
import time
import xarray as xr

from . import utils


@pytest.mark.parametrize(
    "casename, npoints, prefix",
    [
        ("counter_1_0.1", 10, "results.1"),
        ("counter_5_0.2", 25, "results.1"),
        ("counter_output_prefix", 20, "data"),
        ("counter_output_path", 20, os.path.join("newfolder", "results.1")),
    ],
)
def test_counter_npoints(
    casename, npoints, prefix, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    status = utils.job_status(1)["data"][1]["status"]
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        status = utils.job_status(1)["data"][1]["status"]
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    if prefix is not None:
        assert os.path.exists(f"{prefix}.nc")
        ds = xr.load_dataset(f"{prefix}.nc")
        print(f"{ds=}")
        assert ds["uts"].size == npoints


@pytest.mark.parametrize(
    "casename",
    [
        "counter_15_0.1",
    ],
)
def test_counter_cancel(casename, datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    cancel = True
    utils.run_casenames([casename], [None], ["pip-counter"])
    ret = utils.job_status(1)
    status = ret["data"][1]["status"]
    while status in {"q", "qw", "r", "rd"}:
        time.sleep(2)
        if cancel and status == "r":
            subprocess.run(["ketchup", "cancel", "-p", "12345", "1"])
            cancel = False
            time.sleep(2)
        ret = utils.job_status(1)
        status = ret["data"][1]["status"]
    assert status == "cd"


@pytest.mark.parametrize(
    "casename,  external",
    [
        ("counter_15_0.1", True),
        ("counter_snapshot", False),
    ],
)
def test_counter_snapshot(
    casename, external, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    time.sleep(5)
    status = utils.job_status(1)["data"][1]["status"]
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        if external and status == "r":
            subprocess.run(["ketchup", "snapshot", "-p", "12345", "1"])
            external = False
        status = utils.job_status(1)["data"][1]["status"]
    assert status == "c"
    assert os.path.exists("snapshot.1.nc")
