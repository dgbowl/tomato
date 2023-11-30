import json
import os
from pathlib import Path
import yaml
import subprocess
import pytest
import zmq

from tomato import tomato
from tomato.models import Reply

PORT = 12345
CTXT = zmq.Context()


def test_tomato_status_down():
    ret = tomato.status(port=PORT, timeout=1000, context=CTXT)
    print(f"{ret=}")
    assert ret.success == False
    assert "tomato not running" in ret.msg


def test_tomato_status_up(tomato_daemon):
    ret = tomato.status(port=PORT, timeout=1000, context=CTXT)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 2


def test_tomato_start_no_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.start(
        port=PORT, timeout=1000, context=CTXT, appdir=".", logdir=".", verbosity=0
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "settings file not found" in ret.msg


def test_tomato_start_with_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.init(appdir=".", datadir=".")
    assert ret.success
    ret = tomato.start(
        port=PORT, timeout=1000, context=CTXT, appdir=".", logdir=".", verbosity=0
    )
    print(f"{ret=}")
    assert ret.success


def test_tomato_start_double(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.start(
        port=PORT, timeout=1000, context=CTXT, appdir=".", logdir=".", verbosity=0
    )
    print(f"{ret=}")
    assert ret.success == False
    assert f"port {PORT} is already in use" in ret.msg


def test_tomato_reload(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    with open("devices_dummy.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.status(port=PORT, timeout=1000, context=CTXT)
    assert ret.success
    assert len(ret.data) == 2
    ret = tomato.reload(port=PORT, timeout=1000, context=CTXT, appdir=".")
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1


def test_tomato_pipeline(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
        sampleid="test",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready == False

    ret = tomato.pipeline_load(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
        sampleid="abcdefg",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline dummy-5 is not empty" in ret.msg
    assert ret.data.sampleid == "test"

    ret = tomato.pipeline_ready(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_ready(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_eject(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready == False

    ret = tomato.pipeline_eject(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="dummy-5",
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready == False


def test_tomato_pipeline_invalid(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="bogus",
        sampleid="test",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline bogus not found" in ret.msg

    ret = tomato.pipeline_eject(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline bogus not found" in ret.msg

    ret = tomato.pipeline_ready(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline bogus not found" in ret.msg


def test_tomato_log_verbosity_0(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_log_verbosity_default(tomato_daemon, stop_tomato_daemon):
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0
