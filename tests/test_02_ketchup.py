import os

import pytest

from tomato import ketchup, tomato

from . import utils

PORT = 12345

kwargs = {"port": PORT, "timeout": 1000}


@pytest.mark.parametrize(
    "pl, jn",
    [
        ("counter_1_0.1.yml", None),
        ("counter_1_0.1.yml", "counter"),
    ],
)
def test_ketchup_submit_one(pl, jn, datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload=pl, jobname=jn, daemon=daemon)
    assert utils.wait_until_ketchup_status(1, "qw", PORT, 1000)

    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.id == 1
    assert ret.data.jobname == jn


def test_ketchup_submit_two(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", daemon=daemon)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", daemon=daemon)
    assert utils.wait_until_ketchup_status(2, "qw", PORT, 1000)

    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.id == 2
    assert ret.data.jobname == "job-2"


def test_ketchup_status_empty(start_tomato_daemon, stop_tomato_daemon):
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.status(jobids=[], daemon=daemon)
    print(f"{ret=}")
    assert not ret.success
    assert "job queue is empty" in ret.msg


def test_ketchup_status_all_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", daemon=daemon)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", daemon=daemon)
    assert utils.wait_until_ketchup_status(2, "qw", PORT, 1000)

    ret = ketchup.status(jobids=[], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert "found 2" in ret.msg
    assert ret.data is not None
    assert len(ret.data) == 2


def test_ketchup_status_one_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", daemon=daemon)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", daemon=daemon)
    assert utils.wait_until_ketchup_status(2, "qw", PORT, 1000)

    ret = ketchup.status(jobids=[2], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert "found 1" in ret.msg
    assert ret.data is not None
    assert len(ret.data) == 1
    assert ret.data[0].id == 2


def test_ketchup_status_two_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", daemon=daemon)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", daemon=daemon)
    assert utils.wait_until_ketchup_status(2, "qw", PORT, 1000)

    ret = ketchup.status(jobids=[1, 2], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert "found 2" in ret.msg
    assert ret.data is not None
    assert len(ret.data) == 2
    assert ret.data[0].id == 1
    assert ret.data[1].id == 2


def test_ketchup_status_running(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_5_0.2"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)

    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.status(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert "found 1" in ret.msg
    assert ret.data is not None
    assert len(ret.data) == 1
    assert ret.data[0].status == "r"


def test_ketchup_status_complete(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_1_0.1"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)

    assert utils.wait_until_ketchup_status(1, "c", PORT, 5000)

    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.status(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data[0].status == "c"
    assert os.path.exists("results.1.nc")


def test_ketchup_cancel_running(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_60_0.1"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)

    assert utils.wait_until_pickle(jobid=1, timeout=2000)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.cancel(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data[0].status == "rd"

    assert utils.wait_until_ketchup_status(1, "cd", PORT, 5000)
    ret = ketchup.status(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    print(f"{os.listdir()=}")
    print(f"{os.listdir('Jobs')=}")
    print(f"{os.listdir(os.path.join('Jobs', '1'))=}")
    assert ret.data is not None
    assert ret.data[0].status == "cd"
    assert os.path.exists("results.1.nc")


def test_ketchup_cancel_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_60_0.1.yml", jobname=None, daemon=daemon)
    tomato.pipeline_load(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
        sampleid="counter_60_0.1",
    )
    assert utils.wait_until_ketchup_status(1, "qw", PORT, 5000)

    ret = ketchup.cancel(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data[0].status == "cd"


def test_ketchup_snapshot(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_60_0.1"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)

    assert utils.wait_until_pickle(jobid=1, timeout=2000)

    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.snapshot(jobids=[1], daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert os.path.exists("snapshot.1.nc")


def test_ketchup_search(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", daemon=daemon)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", daemon=daemon)

    ret = ketchup.search(jobname="2", daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data) == 1

    ret = ketchup.search(jobname="job", daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data) == 2

    ret = ketchup.search(jobname="wrong", daemon=daemon)
    print(f"{ret=}")
    assert ret.success is False


@pytest.mark.parametrize(
    "pl, jn",
    [
        ("counter_invalid_1.yml", None),
        ("counter_invalid_2.yml", None),
        ("counter_invalid_3.yml", None),
        ("counter_invalid_4.yml", None),
    ],
)
def test_ketchup_validation(pl, jn, datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    daemon = tomato.status(**kwargs).data  # ty: ignore[invalid-argument-type]
    assert daemon is not None

    ret = ketchup.submit(payload=pl, jobname=jn, daemon=daemon)
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.id == 1
    with pytest.raises(AssertionError):
        assert utils.wait_until_ketchup_status(
            jobid=1, status="qw", port=PORT, timeout=1000
        )
