import os
from pathlib import Path
import zmq
import time
import psutil
import logging

from tomato import ketchup, tomato
from .utils import (
    wait_until_tomato_running,
    wait_until_tomato_stopped,
    wait_until_ketchup_status,
    kill_tomato_daemon,
)

PORT = 12345
CTXT = zmq.Context()
WAIT = 5000

kwargs = dict(port=PORT, timeout=1000, context=CTXT)


def test_stop_with_queued_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", **kwargs)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", **kwargs)
    time.sleep(1)
    tomato.stop(**kwargs)
    assert wait_until_tomato_stopped(port=PORT, timeout=5000)
    assert os.path.exists("tomato_state_12345.pkl")

    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 2


def test_stop_with_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_0.2")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)
    ret = tomato.stop(**kwargs)
    print(f"{ret=}")
    assert ret.success is False
    assert "jobs are running" in ret.msg


def test_recover_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="counter_20_5.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_20_5")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)

    ret = tomato.stop(**kwargs)
    kill_tomato_daemon(port=PORT)

    assert os.path.exists("tomato_state_12345.pkl")
    ret = tomato.start(**kwargs, appdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "r"

    assert wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=25000)
    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "c"


def test_recover_waiting_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_0.2")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)

    ret = tomato.stop(**kwargs)
    kill_tomato_daemon(port=PORT)

    time.sleep(5)
    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    assert wait_until_ketchup_status(jobid=1, status="c", port=PORT, timeout=5000)
    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "c"

    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.pips["pip-counter"].jobid is None
    assert ret.data.pips["pip-counter"].sampleid == "counter_5_0.2"


def test_recover_crashed_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="counter_20_5.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_20_5")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    pid = ret.data[0].pid

    ret = tomato.stop(**kwargs)
    kill_tomato_daemon(port=PORT)

    proc = psutil.Process(pid=pid)
    proc.terminate()
    psutil.wait_procs([proc], timeout=3)

    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "ce"

    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.pips["pip-counter"].jobid is None
    assert ret.data.pips["pip-counter"].sampleid == "counter_20_5"
