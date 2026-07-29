import os
import subprocess
from pathlib import Path

import zmq

from tomato import tomato

from . import utils

context = zmq.Context()
PORT = 12345
timeout = 1000
kwargs = {"port": PORT, "timeout": timeout}


def test_tomato_status_down():
    ret = tomato.status(**kwargs)  # ty: ignore[invalid-argument-type]
    print(f"{ret=}")
    assert ret.success is False
    assert "tomato not running" in ret.msg


def test_tomato_status_up(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.status(**kwargs)  # ty: ignore[invalid-argument-type]
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.pipelines) == 1


def test_tomato_start_no_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.start(
        **kwargs,  # ty: ignore[invalid-argument-type]
        appdir=Path(),
        verbosity=0,
    )
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
    assert "settings file not found" in ret.msg


def test_tomato_start_with_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.init(appdir=Path(), datadir=Path(), logdir=Path())
    assert ret.success
    ret = tomato.start(
        **kwargs,  # ty: ignore[invalid-argument-type]
        appdir=Path(),
        verbosity=0,
    )
    print(f"{ret=}")
    assert ret.success


def test_tomato_start_double(datadir, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.start(
        **kwargs,  # ty: ignore[invalid-argument-type]
        appdir=Path(),
        verbosity=0,
    )
    print(f"{ret=}")
    assert ret.success is False
    assert (
        f"port {PORT} is already in use" in ret.msg
        or f"already running on port {PORT}" in ret.msg
    )


def test_tomato_pipeline(datadir, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.pipeline_load(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
        sampleid="test",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.sampleid == "test"
    assert ret.data.ready is False

    ret = tomato.pipeline_load(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
        sampleid="abcdefg",
    )
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'pip-counter' is not empty" in ret.msg
    assert ret.data is not None
    assert ret.data.sampleid == "test"

    ret = tomato.pipeline_ready(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_ready(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_eject(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.sampleid is None
    assert ret.data.ready is False

    ret = tomato.pipeline_eject(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="pip-counter",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.sampleid is None
    assert ret.data.ready is False


def test_tomato_pipeline_invalid(datadir, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.pipeline_load(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="bogus",
        sampleid="test",
    )
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg

    ret = tomato.pipeline_eject(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg

    ret = tomato.pipeline_ready(
        **kwargs,  # ty: ignore[invalid-argument-type]
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline 'bogus' not found" in ret.msg


def test_tomato_log_verbosity_0(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    subprocess.run(
        ["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."],
        check=True,
    )
    subprocess.run(
        ["tomato", "start", "-p", f"{PORT}", "-A", ".", "--quiet"],
        check=True,
    )
    assert utils.wait_until_tomato_running(port=PORT, timeout=5000)
    assert Path("tomato_daemon_12345.log").exists()
    assert Path("tomato_daemon_12345.log").stat().st_size == 0


def test_tomato_log_verbosity_testing(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert utils.wait_until_tomato_running(port=PORT, timeout=5000)
    assert Path("tomato_daemon_12345.log").exists()
    assert Path("tomato_daemon_12345.log").stat().st_size > 0


def test_tomato_log_verbosity_default(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    subprocess.run(
        ["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."],
        check=True,
    )
    subprocess.run(
        ["tomato", "start", "-p", f"{PORT}", "-A", "."],
        check=True,
    )
    assert utils.wait_until_tomato_running(port=PORT, timeout=5000)
    assert Path("tomato_daemon_12345.log").exists()
    assert Path("tomato_daemon_12345.log").stat().st_size > 0


def test_tomato_nocmd(start_tomato_daemon, stop_tomato_daemon):

    req = context.socket(zmq.REQ)
    req.connect("tcp://127.0.0.1:12345")
    req.send_pyobj({"cdm": "typo"})
    rep = req.recv_pyobj()
    print(f"{rep=}")
    assert rep.success is False
    assert "msg without cmd" in rep.msg


def test_tomato_stop(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.stop(**kwargs)  # ty: ignore[invalid-argument-type]
    assert ret.success
    assert utils.wait_until_tomato_stopped(port=PORT, timeout=5000)

    assert Path("tomato_daemon_12345.log").exists()
    with Path("tomato_daemon_12345.log").open() as logf:
        text = logf.read()
    assert "all manager threads joined" in text


def test_tomato_component(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.status(
        **kwargs,  # ty: ignore[invalid-argument-type]
        stgrp="drivers",
        yaml=True,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None

    drv = ret.data["example_counter"]
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = 1000
    req.connect(f"tcp://127.0.0.1:{drv['port']}")

    req.send_pyobj({"cmd": "status", "params": {}})
    ret = req.recv_pyobj()
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1

    params = {"channel": "1", "address": "example-addr"}
    req.send_pyobj({"cmd": "cmp_status", "params": params})
    ret = req.recv_pyobj()
    print(f"{ret=}")
    assert ret.success

    params = {"channel": "2", "address": "example-addr"}
    req.send_pyobj({"cmd": "cmp_status", "params": params})
    ret = req.recv_pyobj()
    print(f"{ret=}")
    assert ret.success is False
    req.close()
