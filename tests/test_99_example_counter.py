import pytest
import os
import subprocess
import json
import yaml
import xarray as xr
import tomato
import zmq
import time

from . import utils

PORT = 12345
CTXT = zmq.Context()


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
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    assert utils.wait_until_ketchup_status(1, "c", PORT, 20000)

    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    if prefix is not None:
        utils.check_npoints_file(f"{prefix}.nc", {"counter": npoints})


@pytest.mark.parametrize(
    "casename",
    [
        "counter_60_0.1",
    ],
)
def test_counter_cancel(casename, datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)

    subprocess.run(["ketchup", "cancel", "-p", "12345", "1"])
    assert utils.wait_until_ketchup_status(1, "cd", PORT, 5000)


@pytest.mark.parametrize(
    "casename,  external",
    [
        ("counter_20_1", True),
        ("counter_snapshot", False),
    ],
)
def test_counter_snapshot_metadata(
    casename, external, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    if external:
        subprocess.run(["ketchup", "snapshot", "-p", "12345", "1"])

    assert utils.wait_until_ketchup_status(1, "c", PORT, 30000)

    assert os.path.exists("snapshot.1.nc")
    utils.sync_files()
    with xr.open_datatree("snapshot.1.nc") as dt:
        assert "tomato_version" in dt.attrs
        assert "tomato_Job" in dt.attrs
        for group in dt:
            assert "tomato_Component" in dt[group].attrs


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
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-vv"])
    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    assert utils.wait_until_tomato_components(port=PORT, timeout=5000)

    utils.run_casenames([casename], [None], ["pip-multidev"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    assert utils.wait_until_ketchup_status(1, "c", PORT, 10000)

    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    assert os.path.exists("results.1.nc")
    utils.check_npoints_file("results.1.nc", npoints)


def test_counter_measure_task_measure(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    kwargs = dict(port=PORT, timeout=1000, context=CTXT)
    ret = tomato.passata.measure(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    assert ret.success

    utils.run_casenames(["counter_5_0.2"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)
    ret = tomato.passata.measure(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    assert not ret.success
    assert "measurement already running" in ret.msg

    assert utils.wait_until_ketchup_status(1, "c", PORT, 10000)
    time.sleep(1)
    ret = tomato.passata.measure(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    assert ret.success
