import json
import os
from pathlib import Path
import yaml
import zmq

from tomato import tomato

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
    ret = tomato.status(**kwargs, with_data=True)
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.pips) == 2


def test_tomato_start_no_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success is False
    assert "settings file not found" in ret.msg


def test_tomato_start_with_init(datadir, stop_tomato_daemon):
    os.chdir(datadir)
    ret = tomato.init(appdir=Path(), datadir=Path())
    assert ret.success
    ret = tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success


def test_tomato_start_double(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.start(**kwargs, appdir=Path(), logdir=Path(), verbosity=0)
    print(f"{ret=}")
    assert ret.success is False
    assert f"port {PORT} is already in use" in ret.msg


def test_tomato_reload(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    with open("devices_dummy.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.status(**kwargs, with_data=True)
    assert ret.success
    assert len(ret.data.pips) == 2

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.pips) == 1
    assert ret.data.devs["dummy_device"].settings == {}

    with open("settings.toml", "a") as inf:
        inf.write("dummy.testpar = 1")
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data.devs["dummy_device"].settings["testpar"] == 1


def test_tomato_pipeline(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="test")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready is False

    ret = tomato.pipeline_load(**kwargs, pipeline="dummy-5", sampleid="abcdefg")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline dummy-5 is not empty" in ret.msg
    assert ret.data.sampleid == "test"

    ret = tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_ready(**kwargs, pipeline="dummy-5")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid == "test"
    assert ret.data.ready

    ret = tomato.pipeline_eject(**kwargs, pipeline="dummy-5")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready is False

    ret = tomato.pipeline_eject(**kwargs, pipeline="dummy-5")
    print(f"{ret=}")
    assert ret.success
    assert ret.data.sampleid is None
    assert ret.data.ready is False


def test_tomato_pipeline_invalid(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    ret = tomato.pipeline_load(**kwargs, pipeline="bogus", sampleid="test")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline bogus not found" in ret.msg

    ret = tomato.pipeline_eject(**kwargs, pipeline="bogus")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline bogus not found" in ret.msg

    ret = tomato.pipeline_ready(**kwargs, pipeline="bogus")
    print(f"{ret=}")
    assert ret.success is False
    assert "pipeline bogus not found" in ret.msg


def test_tomato_log_verbosity_0(datadir, stop_tomato_daemon):
    test_tomato_start_with_init(datadir, stop_tomato_daemon)
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_log_verbosity_default(start_tomato_daemon, stop_tomato_daemon):
    assert Path("daemon_12345.log").exists()
    assert Path("daemon_12345.log").stat().st_size > 0


def test_tomato_nocmd(start_tomato_daemon, stop_tomato_daemon):
    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.connect("tcp://127.0.0.1:12345")
    req.send_pyobj(dict(cdm="typo"))
    rep = req.recv_pyobj()
    print(f"{rep=}")
    assert rep.success is False
    assert "msg without cmd" in rep.msg
