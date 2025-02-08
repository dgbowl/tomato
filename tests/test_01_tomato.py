import os
from pathlib import Path
import zmq
import subprocess

from tomato import tomato
from .utils import wait_until_tomato_running, wait_until_tomato_stopped

PORT = 12345
CTXT = zmq.Context()
timeout = 1000
kwargs = dict(port=PORT, context=CTXT, timeout=timeout)


def test_tomato_status_down():
    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success is False
    assert "tomato not running" in ret.msg


def test_tomato_status_up(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.status(**kwargs)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.pips) == 1


def test_tomato_start_no_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.start(**kwargs, appdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success is False
    assert "settings file not found" in ret.msg


def test_tomato_start_with_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.init(appdir=Path(), datadir=Path(), logdir=Path())
    assert ret.success
    ret = tomato.start(**kwargs, appdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success


def test_tomato_start_double(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    ret = tomato.start(**kwargs, appdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success is False
    assert (
        f"port {PORT} is already in use" in ret.msg
        or f"already running on port {PORT}" in ret.msg
    )


def test_tomato_pipeline(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="test")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready is False

    ret = tomato.pipeline_load(**kwargs, pipeline="pip-counter", sampleid="abcdefg")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'pip-counter' is not empty" in ret.msg
    assert ret.data.sampleid == "test"

    ret = tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_ready(**kwargs, pipeline="pip-counter")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_eject(**kwargs, pipeline="pip-counter")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready is False

    ret = tomato.pipeline_eject(**kwargs, pipeline="pip-counter")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready is False


def test_tomato_pipeline_invalid(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(**kwargs, pipeline="bogus", sampleid="test")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg

    ret = tomato.pipeline_eject(**kwargs, pipeline="bogus")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg

    ret = tomato.pipeline_ready(**kwargs, pipeline="bogus")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg


def test_tomato_log_verbosity_0(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_log_verbosity_testing(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_log_verbosity_default(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", "."])
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_nocmd(start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    req = CTXT.socket(zmq.REQ)
    req.connect("tcp://127.0.0.1:12345")
    req.send_pyobj(dict(cdm="typo"))
    rep = req.recv_pyobj()
    print(f"{rep=}")
    assert rep.success is False
    assert "msg without cmd" in rep.msg


def test_tomato_stop(start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=5000)
    ret = tomato.stop(**kwargs)
    assert ret.success
    assert wait_until_tomato_stopped(port=PORT, timeout=5000)

    assert Path("daemon_12345.log").exists()
    with Path("daemon_12345.log").open() as logf:
        text = logf.read()
    assert "driver manager thread joined" in text
    assert "job manager thread joined" in text
