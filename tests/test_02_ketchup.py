import os
import pytest
import zmq

from tomato import ketchup, tomato
from .utils import wait_until_tomato_running, wait_until_ketchup_status

PORT = 12345
CTXT = zmq.Context()

kwargs = dict(port=PORT, timeout=1000, context=CTXT)


@pytest.mark.parametrize(
    "pl, jn",
    [
        ("counter_1_0.1.yml", None),
        ("counter_1_0.1.yml", "counter"),
    ],
)
def test_ketchup_submit_one(pl, jn, datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    os.chdir(datadir)
    ret = ketchup.submit(**kwargs, payload=pl, jobname=jn)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.id == 1
    assert ret.data.jobname == jn


def test_ketchup_submit_two(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_one("counter_1_0.1.yml", "job-1", *args)
    ret = ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", **kwargs)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.id == 2
    assert ret.data.jobname == "job-2"


def test_ketchup_status_empty(start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[])
    print(f"{ret=}")
    assert not ret.success
    assert "job queue is empty" in ret.msg


def test_ketchup_status_all_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_two(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[])
    print(f"{ret=}")
    assert ret.success
    assert "found 2" in ret.msg
    assert len(ret.data) == 2


def test_ketchup_status_one_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_two(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[2])
    print(f"{ret=}")
    assert ret.success
    assert "found 1" in ret.msg
    assert len(ret.data) == 1
    assert 2 in ret.data.keys()


def test_ketchup_status_two_queued(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_two(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[1, 2])
    print(f"{ret=}")
    assert ret.success
    assert "found 2" in ret.msg
    assert len(ret.data) == 2
    assert 1 in ret.data.keys()
    assert 2 in ret.data.keys()


@pytest.mark.parametrize(
    "pl",
    [
        "counter_5_0.2",
    ],
)
def test_ketchup_status_running(pl, datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_one(f"{pl}.yml", None, *args)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid=pl)
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=5000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[1])
    print(f"{ret=}")
    assert ret.success
    assert "found 1" in ret.msg
    assert len(ret.data) == 1
    assert ret.data[1].status == "r"


@pytest.mark.parametrize(
    "pl",
    [
        "counter_1_0.1",
    ],
)
def test_ketchup_status_complete(pl, datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_one(f"{pl}.yml", None, *args)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid=pl)
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=10000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[1])
    print(f"{ret=}")
    assert ret.success
    assert ret.data[1].status == "c"
    assert os.path.exists("results.1.nc")

import time

@pytest.mark.parametrize(
    "pl",
    [
        "counter_15_0.1",
    ],
)
def test_ketchup_cancel(pl, datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_status_running(pl, *args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.cancel(**kwargs, status=status, verbosity=0, jobids=[1])
    print(f"{ret=}")
    assert ret.success
    assert ret.data[1].status == "rd"
    wait_until_ketchup_status(jobid=1, status="cd", port=PORT, timeout=5000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[1])
    print(f"{ret=}")
    assert ret.data[1].status == "cd"
    time.sleep(5)
    assert os.path.exists("results.1.nc")


@pytest.mark.parametrize(
    "pl",
    [
        "counter_15_0.1",
    ],
)
def test_ketchup_snapshot(pl, datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_status_running(pl, *args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.snapshot(jobids=[1], status=status)
    print(f"{ret=}")
    assert ret.success
    time.sleep(5)
    assert os.path.exists("snapshot.1.nc")


def test_ketchup_search(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_two(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.search(jobname="2", status=status)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1

    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.search(jobname="job", status=status)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 2

    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.search(jobname="wrong", status=status)
    print(f"{ret=}")
    assert ret.success is False
