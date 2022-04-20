import pytest
import json
import os
import subprocess
import time
import signal

from . import utils


@pytest.mark.parametrize(
    "casename, npoints",
    [
        (
            "dummy_random_2_0.1",
            20,
        ),
        (
            "dummy_random_5_2",
            3,
        ),
    ],
)
def test_run_dummy_random(casename, npoints, datadir):
    os.chdir(datadir)
    status = utils.run_casename(casename)
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "jobdata.log" in files
    data = []
    for file in files:
        if file.endswith("_data.json"):
            with open(os.path.join(".", "Jobs", "1", file), "r") as of:
                jsdata = json.load(of)
                for point in jsdata["data"]:
                    data.append(point)
    assert len(data) == npoints
