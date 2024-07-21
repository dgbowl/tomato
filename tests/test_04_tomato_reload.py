import json
from pathlib import Path
import yaml
import zmq

from tomato import tomato
from .utils import wait_until_tomato_running

PORT = 12345
CTXT = zmq.Context()
timeout = 1000
kwargs = dict(port=PORT, context=CTXT, timeout=timeout)


def test_reload_noop(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)
    ret = tomato.reload(**kwargs, appdir=Path())
    assert ret.success
    assert len(ret.data.drvs) == 1
    assert len(ret.data.devs) == 1
    assert len(ret.data.pips) == 1
    assert len(ret.data.cmps) == 1


def test_reload_settings(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)

    with open("settings.toml", "a") as inf:
        inf.write("example_counter.testparb = 1")
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.drvs) == 1
    assert len(ret.data.devs) == 1
    assert len(ret.data.pips) == 1
    assert len(ret.data.cmps) == 1
    assert ret.data.drvs["example_counter"].settings == {"testpar": 1234, "testparb": 1}


def test_reload_cmps_pips(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)

    with open("devices_counter.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.drvs) == 1
    assert len(ret.data.devs) == 1
    assert len(ret.data.pips) == 4
    assert len(ret.data.cmps) == 4


def test_reload_devs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)

    with open("devices_multidev.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.drvs) == 1
    assert len(ret.data.devs) == 2
    assert len(ret.data.pips) == 2
    assert len(ret.data.cmps) == 3


def test_reload_drvs(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)

    with open("devices_psutil.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert len(ret.data.drvs) == 2
    assert len(ret.data.devs) == 2
    assert len(ret.data.pips) == 1
    assert len(ret.data.cmps) == 2
