import os
from pathlib import Path
import zmq
import time
import psutil

from tomato import ketchup, tomato
from .utils import wait_until_tomato_running, wait_until_ketchup_status

PORT = 12345
CTXT = zmq.Context()
WAIT = 5000

kwargs = dict(port=PORT, timeout=1000, context=CTXT)


def test_recover_queued_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-2", **kwargs)
    tomato.stop(**kwargs)
    assert not wait_until_tomato_running(port=PORT, timeout=100)
    assert os.path.exists("tomato_state_12345.pkl")

    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 2
    assert ret.data.nextjob == 3


def test_recover_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="dummy_random_5_2")
    tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)
    tomato.stop(**kwargs)
    assert not wait_until_tomato_running(port=PORT, timeout=100)
    assert os.path.exists("tomato_state_12345.pkl")

    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 1
    assert ret.data.nextjob == 2
    assert ret.data.jobs[1].status == "r"


def test_recover_waiting_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="dummy_random_5_2")
    tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)
    tomato.stop(**kwargs)
    assert not wait_until_tomato_running(port=PORT, timeout=100)
    assert os.path.exists("tomato_state_12345.pkl")

    time.sleep(10)

    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 1
    assert ret.data.nextjob == 2
    assert ret.data.jobs[1].status == "c"


def test_prune_crashed_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_30_1.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="dummy_random_30_1")
    tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=WAIT)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    tomato.stop(**kwargs)
    assert not wait_until_tomato_running(port=PORT, timeout=100)
    assert os.path.exists("tomato_state_12345.pkl")

    proc = psutil.Process(pid=ret.data.jobs[1].pid)
    proc.terminate()
    time.sleep(5)

    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    assert wait_until_tomato_running(port=PORT, timeout=WAIT)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 1
    assert ret.data.nextjob == 2
    assert ret.data.jobs[1].status == "ce"
