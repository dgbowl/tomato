import pytest
import os
import subprocess
import xarray as xr
from datetime import datetime
from tomato.models import Job
from . import utils

PORT = 12345


@pytest.mark.parametrize(
    "case, nreps",
    [
        ("counter_stresstest", 5),
    ],
)
def test_stresstest(case, nreps, datadir, stop_tomato_daemon):
    os.chdir(datadir)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", "."])
    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    assert utils.wait_until_tomato_components(port=PORT, timeout=5000)

    subprocess.run(["tomato", "pipeline", "load", "-p", f"{PORT}", "pip-counter", case])
    for i in range(nreps):
        subprocess.run(["ketchup", "submit", "-p", f"{PORT}", f"{case}.yml"])

    subprocess.run(["tomato", "pipeline", "ready", "-p", f"{PORT}", "pip-counter"])

    utils.wait_until_ketchup_status(jobid=nreps, status="c", port=PORT, timeout=40000)

    prev = None
    for i in range(nreps):
        i += 1
        assert os.path.exists(f"results.{i}.nc")
        with xr.open_datatree(f"results.{i}.nc") as dt:
            completed_at = Job.model_validate_json(dt.attrs["tomato_Job"]).completed_at
        ti = datetime.fromisoformat(completed_at)
        if prev is not None:
            assert ti > prev
        prev = ti
