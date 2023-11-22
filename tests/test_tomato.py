import json
import os
import yaml
import subprocess
import pytest
import zmq

from tomato.main import (
    tomato_status,
    tomato_start,
    tomato_init,
    tomato_reload,
    tomato_pipeline_eject,
    tomato_pipeline_load,
    tomato_pipeline_ready,
)
from tomato.models import Reply

PORT = 12345
CTXT = zmq.Context()


def test_tomato_status_down():
    ret = tomato_status(port=PORT, timeout=1000, context=CTXT)
    print(f"{ret=}")
    assert ret.success == False
    assert "tomato not running" in ret.msg


def test_tomato_status_up(tomato_daemon):
    ret = tomato_status(port=PORT, timeout=1000, context=CTXT)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 2


def test_tomato_start_no_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato_start(port=PORT, timeout=1000, context=CTXT, appdir=".")
    print(f"{ret=}")
    assert ret.success == False
    assert "settings file not found" in ret.msg


def test_tomato_start_with_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato_init(appdir=".", datadir=".")
    assert ret.success
    ret = tomato_start(port=PORT, timeout=1000, context=CTXT, appdir=".")
    print(f"{ret=}")
    assert ret.success


def test_tomato_start_double(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato_start(port=PORT, timeout=1000, context=CTXT, appdir=".")
    print(f"{ret=}")
    assert ret.success == False
    assert f"port {PORT} is already in use" in ret.msg


def test_tomato_reload(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    with open("devices_dummy.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato_status(port=PORT, timeout=1000, context=CTXT)
    assert ret.success
    assert len(ret.data) == 2
    ret = tomato_reload(port=PORT, timeout=1000, context=CTXT, appdir=".")
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data) == 1


def test_tomato_pipeline(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato_pipeline_load(
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

    ret = tomato_pipeline_load(
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

    ret = tomato_pipeline_ready(
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

    ret = tomato_pipeline_ready(
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

    ret = tomato_pipeline_eject(
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

    ret = tomato_pipeline_eject(
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
    ret = tomato_pipeline_load(
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

    ret = tomato_pipeline_eject(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline bogus not found" in ret.msg

    ret = tomato_pipeline_ready(
        port=PORT,
        timeout=1000,
        context=CTXT,
        appdir=".",
        pipeline="bogus",
    )
    print(f"{ret=}")
    assert ret.success == False
    assert "pipeline bogus not found" in ret.msg
