import pytest
import os
import subprocess
import time
import json
import yaml
import xarray as xr

from . import utils

PORT = 12345


@pytest.mark.parametrize(
    "casename, npoints, prefix",
    [
        ("counter_1_0.1", 10, "results.1"),
        ("counter_5_0.2", 25, "results.1"),
        ("counter_output_prefix", 20, "data"),
        ("counter_output_path", 20, os.path.join("newfolder", "results.1")),
        ("counter_multistep", 15, "results.1"),
    ],
)
def test_counter_npoints_metadata(
    casename, npoints, prefix, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    status = utils.job_status(1)
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        status = utils.job_status(1)
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    if prefix is not None:
        assert os.path.exists(f"{prefix}.nc")
        dt = xr.open_datatree(f"{prefix}.nc")
        ds = dt["counter"]
        print(f"{ds=}")
        assert ds["uts"].size == npoints
        assert "tomato_version" in dt.attrs
        assert "tomato_Job" in dt.attrs


@pytest.mark.parametrize(
    "casename",
    [
        "counter_60_0.1",
    ],
)
def test_counter_cancel(casename, datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    cancel = True
    utils.run_casenames([casename], [None], ["pip-counter"])
    status = utils.job_status(1)
    while status in {"q", "qw", "r", "rd"}:
        time.sleep(2)
        if cancel and status == "r":
            subprocess.run(["ketchup", "cancel", "-p", "12345", "1"])
            cancel = False
            time.sleep(2)
        status = utils.job_status(1)
    assert status == "cd"


@pytest.mark.parametrize(
    "casename,  external",
    [
        ("counter_60_0.1", True),
        ("counter_snapshot", False),
    ],
)
def test_counter_snapshot_metadata(
    casename, external, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    time.sleep(5)
    status = utils.job_status(1)
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        if external and status == "r":
            subprocess.run(["ketchup", "snapshot", "-p", "12345", "1"])
            external = False
        status = utils.job_status(1)
    assert status == "c"
    assert os.path.exists("snapshot.1.nc")
    dt = xr.open_datatree("snapshot.1.nc")
    assert "tomato_version" in dt.attrs
    assert "tomato_Job" in dt.attrs


@pytest.mark.parametrize(
    "casename, npoints",
    [
        ("counter_multidev", {"counter-1": 10, "counter-2": 5}),
        ("counter_multistep_multidev", {"counter-1": 10, "counter-2": 20}),
    ],
)
def test_counter_multidev(casename, npoints, datadir, stop_tomato_daemon):
    os.chdir(datadir)
    with open("devices_multidev.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-L", ".", "-vv"])
    utils.wait_until_tomato_running(port=PORT, timeout=3000)

    utils.run_casenames([casename], [None], ["pip-multidev"])
    utils.wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=10000)
    utils.wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=10000)

    status = utils.job_status(1)
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    assert os.path.exists("results.1.nc")
    dt = xr.open_datatree("results.1.nc")
    for group, points in npoints.items():
        print(f"{dt[group]=}")
        assert dt[group]["uts"].size == points
