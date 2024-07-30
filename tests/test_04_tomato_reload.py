import json
from pathlib import Path
import yaml
import zmq

from tomato import tomato
from .utils import wait_until_tomato_running, wait_until_ketchup_status, run_casenames

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

    # Let's add psutil driver / device
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

    # Let's remove psutil driver / device and modify channels
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


def test_reload_running(datadir, start_tomato_daemon, stop_tomato_daemon):
    assert wait_until_tomato_running(port=PORT, timeout=timeout)

    run_casenames(["counter_20_5"], [None], ["pip-counter"])
    assert wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=5000)

    # Try modifying settings of a driver in use
    with open("settings.toml", "a") as inf:
        inf.write("example_counter.testparb = 1")
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would modify a driver of a device in a running pipeline" in ret.msg

    # Revert settings.toml back
    with open("settings.toml", "r") as inf:
        lines = inf.readlines()
    with open("settings.toml", "w") as out:
        out.writelines(lines[:-1])
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success

    # Try modifying device driver
    with open("devices_reload_driver.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try removing channel on device
    with open("devices_reload_channel.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try modifying address on device
    with open("devices_reload_address.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try removing pipeline
    with open("devices_reload_pipdel.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would delete a running pipeline" in ret.msg

    # Try modifying pipeline
    with open("devices_reload_pipmod.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert "reload would modify components of a running pipeline" in ret.msg
