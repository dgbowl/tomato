import os
from pathlib import Path
import zmq
import time

from tomato import ketchup, tomato

PORT = 12345
CTXT = zmq.Context()

kwargs = dict(port=PORT, timeout=1000, context=CTXT)


def test_recover_queued_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-2", **kwargs)
    tomato.stop(**kwargs)
    assert os.path.exists("tomato_state_12345.pkl")
    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 2
    assert ret.data.nextjob == 3


def test_recover_running_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="dummy_random_5_2")
    tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    time.sleep(2)
    tomato.stop(**kwargs)
    assert os.path.exists("tomato_state_12345.pkl")
    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 1
    assert ret.data.nextjob == 2
    assert ret.data.jobs[1].status == "r"


def test_recover_waiting_jobs(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    ketchup.submit(payload="dummy_random_5_2.yml", jobname="job-1", **kwargs)
    tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="dummy_random_5_2")
    tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    time.sleep(2)
    tomato.stop(**kwargs)
    assert os.path.exists("tomato_state_12345.pkl")
    time.sleep(5)
    tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    time.sleep(2)
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.jobs) == 1
    assert ret.data.nextjob == 2
    assert ret.data.jobs[1].status == "c"
