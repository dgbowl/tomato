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
    ret = ketchup.submit(payload="counter_5_1.yml", jobname="job-2", **kwargs)
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


def test_ketchup_status_running(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_submit_two(*args)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_1")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    wait_until_ketchup_status(jobid=2, status="r", port=PORT, timeout=5000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[1, 2])
    print(f"{ret=}")
    assert ret.success
    assert "found 2" in ret.msg
    assert len(ret.data) == 2
    assert ret.data[1].status == "qw"
    assert ret.data[2].status == "r"


def test_ketchup_status_complete(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_status_running(*args)
    wait_until_ketchup_status(jobid=2, status="c", port=PORT, timeout=30000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[2])
    print(f"{ret=}")
    assert ret.success
    assert ret.data[2].status == "c"


def test_ketchup_cancel(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_status_running(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.cancel(**kwargs, status=status, verbosity=0, jobids=[1, 2])
    print(f"{ret=}")
    assert ret.success
    assert ret.data[1].status == "cd"
    assert ret.data[2].status == "rd"
    wait_until_ketchup_status(jobid=2, status="cd", port=PORT, timeout=5000)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.status(**kwargs, status=status, verbosity=0, jobids=[2])
    print(f"{ret=}")
    assert ret.data[2].status == "cd"


def test_ketchup_snapshot(datadir, start_tomato_daemon, stop_tomato_daemon):
    args = [datadir, start_tomato_daemon, stop_tomato_daemon]
    test_ketchup_status_running(*args)
    status = tomato.status(**kwargs, with_data=True)
    ret = ketchup.snapshot(jobids=[2], status=status)
    print(f"{ret=}")
    assert ret.success
    assert os.path.exists("snapshot.2.json")


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
