import pytest
import os
import subprocess
import json
import yaml
import xarray as xr
import zmq
import time
from tomato import tomato


from . import utils

PORT = 12345
CTXT = zmq.Context()


@pytest.mark.parametrize(
    "casename, npoints",
    [
        ("psutil_1_0.1", {"psutil": 10}),
        ("psutil_counter", {"psutil": 12, "counter": 10}),
        ("psutil_counter_with_task_start", {"psutil": 12, "counter": 10}),
        ("psutil_counter_with_task_stop", {"psutil": 10, "counter": 2}),
    ],
)
def test_psutil_multidev(casename, npoints, datadir, stop_tomato_daemon):
    os.chdir(datadir)
    with open("devices_psutil.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-vv"])

    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    assert utils.wait_until_tomato_components(port=PORT, timeout=5000)

    utils.run_casenames([casename], [None], ["pip-multidev"])
    assert utils.wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=2e4)

    status = utils.job_status(1)
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    assert os.path.exists("results.1.nc")
    time.sleep(1)
    dt = xr.open_datatree("results.1.nc")
    for group, points in npoints.items():
        print(f"{dt[group]=}")
        assert dt[group]["uts"].size == points


def test_psutil_passata(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    with open("devices_psutil.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-vv"])
    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)

    ret = tomato.status(port=PORT, timeout=1000, context=CTXT, stgrp="drivers")
    assert ret.success
    assert ret.data["psutil"].version == "1.0"

    ret = subprocess.run(
        ["passata", "status", "psutil:(psutil-addr,10)", "-p", f"{PORT}"],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert "Success: component ('psutil-addr', '10') is not running" in ret.stdout

    ret = subprocess.run(
        ["passata", "attrs", "psutil:(psutil-addr,10)", "-p", f"{PORT}"],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert "Success: attrs of component ('psutil-addr', '10') are" in ret.stdout

    ret = subprocess.run(
        ["passata", "constants", "psutil:(psutil-addr,10)", "-p", f"{PORT}"],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert (
        "Failure: driver of component 'psutil:(psutil-addr,10)' is on version 1.0"
        in ret.stdout
    )
