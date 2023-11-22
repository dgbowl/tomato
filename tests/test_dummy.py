import pytest
import json
import os
import subprocess
import yaml
import time

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
def test_run_dummy_random(casename, npoints, prefix, datadir, tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["dummy-10"])
    status = utils.job_status(1)["data"][0]["status"]
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        status = utils.job_status(1)["data"][0]["status"]
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
def test_run_dummy_jobname(casename, jobname, search, datadir, tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames([casename], [jobname], ["dummy-10"])
    status = utils.job_status(1)["data"][0]["status"]
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        if search:
            ret = subprocess.run(
                ["ketchup", "search", "-p", "12345", "--appdir", ".", "$MATCH"],
                capture_output=True,
                text=True,
            )
            yml = yaml.safe_load(ret.stdout)
            print(f"{yml=}")
            assert yml["data"][0]["jobname"] == jobname
            search = False
        status = utils.job_status(1)["data"][0]["status"]
    assert status == "c"
    ret = subprocess.run(
        ["ketchup", "status", "-p", "12345", "--appdir", ".", "1"],
        capture_output=True,
        text=True,
    )
    yml = yaml.safe_load(ret.stdout)
    print(f"{yml=}")
    assert yml["data"][0]["jobname"] == jobname


@pytest.mark.parametrize(
    "casename",
    [
        "dummy_random_30_1",
    ],
)
def test_run_dummy_cancel(casename, datadir, tomato_daemon):
    os.chdir(datadir)
    cancel = True
    utils.run_casenames([casename], [None], ["dummy-10"])
    status = utils.job_status(1)["data"][0]["status"]
    print(f"{status=}")
    while status in {"q", "qw", "r", "rd"}:
        time.sleep(2)
        if cancel and status == "r":
            subprocess.run(["ketchup", "cancel", "-p", "12345", "--appdir", ".", "1"])
            cancel = False
            time.sleep(2)
        ret = utils.job_status(1)
        print(f"{ret=}")
        status = ret["data"][0]["status"]

    assert status == "cd"


@pytest.mark.parametrize(
    "casename,  external",
    [
        ("dummy_sequential_20_10", True),
        ("dummy_sequential_snapshot_30_5", False),
    ],
)
def test_run_dummy_snapshot(casename, external, datadir, tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["dummy-10"])
    time.sleep(10)
    status = utils.job_status(1)["data"][0]["status"]
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        if external and status == "r":
            subprocess.run(["ketchup", "snapshot", "-p", "12345", "--appdir", ".", "1"])
            external = False
        status = utils.job_status(1)["data"][0]["status"]
    assert status == "c"
    assert os.path.exists("snapshot.1.json")
    assert os.path.exists("snapshot.1.zip")


def test_run_dummy_multiple(datadir, tomato_daemon):
    os.chdir(datadir)
    casenames = ["dummy_random_5_2", "dummy_random_1_0.1"]
    jobnames = ["job one", "job two"]
    pipelines = ["dummy-10", "dummy-5"]
    utils.run_casenames(casenames, jobnames, pipelines)
    status = utils.job_status(1)["data"][0]["status"]
    print(f"{status=}")
    while status in {"q", "qw", "r"}:
        time.sleep(1)
        status = utils.job_status(1)["data"][0]["status"]
    ret = subprocess.run(
        ["ketchup", "status", "-p", "12345", "--appdir", ".", "1", "2"],
        capture_output=True,
        text=True,
    )
    yml = yaml.safe_load(ret.stdout)
    assert len(yml["data"]) == 2
    assert {1, 2} == set([i["jobid"] for i in yml["data"]])
    assert set(jobnames) == set([i["jobname"] for i in yml["data"]])
    assert {"c"} == set([i["status"] for i in yml["data"]])
