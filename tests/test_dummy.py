import pytest
import json
import os
import subprocess
import yaml

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


@pytest.mark.parametrize(
    "casename, jobname, search",
    [
        ("dummy_random_1_0.1", "custom_name", False),
        ("dummy_random_30_1", "$MATCH_custom_name", True),
    ],
)
def test_run_dummy_jobname(casename, jobname, search, datadir):
    os.chdir(datadir)
    if search:
        status = utils.run_casename(
            casename, jobname=jobname, inter_func=utils.search_job
        )
    else:
        status = utils.run_casename(casename, jobname=jobname)
    assert status == "c"
    ret = subprocess.run(
        ["ketchup", "-t", "status", "1"],
        capture_output=True,
        text=True,
    )
    for line in ret.stdout.split("\n"):
        if line.startswith("jobname"):
            assert line.split("=")[1].strip() == jobname


@pytest.mark.parametrize(
    "casename",
    [
        "dummy_random_30_1",
    ],
)
def test_run_dummy_cancel(casename, datadir):
    os.chdir(datadir)
    status = utils.run_casename(casename, inter_func=utils.cancel_job)
    assert status == "cd"


@pytest.mark.parametrize(
    "casename, external",
    [
        ("dummy_sequential_20_10", True),
        ("dummy_sequential_snapshot_30_5", False),
    ],
)
def test_run_dummy_snapshot(casename, external, datadir):
    os.chdir(datadir)
    if external:
        status = utils.run_casename(casename, inter_func=utils.snapshot_job)
    else:
        status = utils.run_casename(casename)
    assert status == "c"
    assert os.path.exists("snapshot.1.json")
    assert os.path.exists("snapshot.1.zip")


def test_run_dummy_multiple(datadir):
    os.chdir(datadir)
    casenames = ["dummy_random_5_2", "dummy_random_1_0.1"]
    jobnames = ["job one", "job two"]
    utils.run_casename(casename=casenames, jobname=jobnames)
    ret = subprocess.run(
        ["ketchup", "-t", "status", "1", "2"],
        capture_output=True,
        text=True,
    )
    yml = yaml.safe_load(ret.stdout)
    assert len(yml) == 2
    assert {1, 2} == set([i["jobid"] for i in yml])
    assert set(jobnames) == set([i["jobname"] for i in yml])
    assert {"c"} == set([i["status"] for i in yml])
