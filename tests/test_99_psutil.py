import pytest
import os
import subprocess
import json
import yaml
import xarray as xr

from . import utils

PORT = 12345


@pytest.mark.parametrize(
    "casename, npoints",
    [
        ("psutil_1_0.1", {"psutil": 10}),
        ("psutil_counter", {"psutil": 12, "counter": 10}),
    ],
)
def test_psutil_multidev(casename, npoints, datadir, stop_tomato_daemon):
    os.chdir(datadir)
    with open("devices_psutil.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-L", ".", "-vv"])
    utils.wait_until_tomato_running(port=PORT, timeout=3000)

    utils.run_casenames([casename], [None], ["pip-multidev"])
    utils.wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=2000)
    utils.wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=2000)

    ret = utils.job_status(1)
    print(f"{ret=}")
    status = utils.job_status(1)["data"][1]["status"]
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "job-1.log" in files
    assert os.path.exists("results.1.nc")
    for group, points in npoints.items():
        ds = xr.load_dataset("results.1.nc", group=group)
        print(f"{ds=}")
        assert ds["uts"].size == points
