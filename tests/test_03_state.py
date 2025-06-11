import os
from pathlib import Path
import zmq
import time
import psutil
import logging

from tomato import ketchup, tomato
from . import utils

PORT = 12345
CTXT = zmq.Context()
WAIT = 10000

kwargs = dict(port=PORT, timeout=1000, context=CTXT)


def test_stop_with_queued_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_1_0.1.yml", jobname="job-1", **kwargs)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-2", **kwargs)

    time.sleep(1)
    tomato.stop(**kwargs)
    assert utils.wait_until_tomato_stopped(port=PORT, timeout=5000)
    assert os.path.exists("tomato_state_12345.pkl")

    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert utils.wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 2


def test_stop_with_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_0.2")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert utils.wait_until_ketchup_status(1, "r", PORT, WAIT)

    ret = tomato.stop(**kwargs)
    print(f"{ret=}")
    assert ret.success is False
    assert "jobs are running" in ret.msg


def test_restart_with_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_20_5.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_20_5")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert utils.wait_until_ketchup_status(1, "r", PORT, WAIT)

    ret = tomato.stop(**kwargs)
    utils.kill_tomato_daemon(port=PORT)

    assert os.path.exists("tomato_state_12345.pkl")
    ret = tomato.start(**kwargs, appdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert utils.wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = ketchup.status(**kwargs, jobids=[], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "r"

    assert utils.wait_until_ketchup_status(1, "c", PORT, 25000)
    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1
    assert ret.data[0].status == "c"


def test_restart_with_complete_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_0.2")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert utils.wait_until_ketchup_status(1, "r", PORT, timeout=WAIT)

    ret = tomato.stop(**kwargs)
    utils.kill_tomato_daemon(port=PORT)

    time.sleep(5)
    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_ketchup_status(1, "c", PORT, 5000)

    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.pips["pip-counter"].jobid is None
    assert ret.data.pips["pip-counter"].sampleid == "counter_5_0.2"


def test_restart_with_crashed_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_20_5.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_20_5")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert utils.wait_until_ketchup_status(1, "r", PORT, WAIT)

    ret = ketchup.status(**kwargs, jobids=[1], verbosity=logging.DEBUG)
    print(f"{ret=}")
    pid = ret.data[0].pid

    ret = tomato.stop(**kwargs)
    utils.kill_tomato_daemon(port=PORT)
    proc = psutil.Process(pid=pid)
    proc.terminate()
    psutil.wait_procs([proc], timeout=3)

    tomato.start(**kwargs, appdir=Path(), verbosity=0)
    assert utils.wait_until_tomato_running(port=PORT, timeout=WAIT)
    assert utils.wait_until_ketchup_status(1, "ce", PORT, 5000)

    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success
    assert ret.data.pips["pip-counter"].jobid is None
    assert ret.data.pips["pip-counter"].sampleid == "counter_20_5"


def test_crashed_driver_restarts(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.status(**kwargs, stgrp="drivers")
    assert ret.success
    print(f"{ret.data=}")

    pid = ret.data["example_counter"].pid
    p = psutil.Process(pid)
    p.terminate()
    gone, alive = psutil.wait_procs([p], timeout=5)
    print(f"{gone=}")
    print(f"{alive=}")
    time.sleep(5)

    ret = tomato.status(**kwargs, stgrp="drivers")
    assert ret.success
    print(f"{ret.data=}")
    assert pid != ret.data["example_counter"].pid


def test_crashed_driver_with_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="counter_5_0.2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="counter_5_0.2")
    tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    assert utils.wait_until_ketchup_status(1, "r", PORT, WAIT)

    ret = tomato.status(**kwargs, stgrp="drivers")
    assert ret.success
    print(f"{ret.data=}")
    pid = ret.data["example_counter"].pid
    p = psutil.Process(pid)
    p.terminate()
    gone, alive = psutil.wait_procs([p], timeout=5)
    print(f"{gone=}")
    print(f"{alive=}")

    assert utils.wait_until_ketchup_status(1, "ce", PORT, 5000)
