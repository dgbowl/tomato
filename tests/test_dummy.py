import pytest
import json
import os
import subprocess
import time
import signal

from . import utils


@pytest.mark.parametrize(
    "casename, npoints, prefix",
    [
        (
            "dummy_random_2_0.1",
            20,
            "results.1",
        ),
        (
            "dummy_random_5_2",
            3,
            "results.1",
        ),
        (
            "dummy_sequential_1_0.05",
            20,
            "data",
        ),
        (
            "dummy_random_1_0.1",
            10,
            os.path.join("newfolder", "results.1"),
        ),
    ],
)
def test_run_dummy_random(casename, npoints, prefix, datadir):
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
    if prefix is not None:
        assert os.path.exists(f"{prefix}.json")
        assert os.path.exists(f"{prefix}.zip")
        with open(f"{prefix}.json", "r") as of:
            dg = json.load(of)
        assert len(dg["steps"][0]["data"]) == npoints
