import json
from pathlib import Path

import yaml

from tomato import tomato

from . import utils

PORT = 12345
timeout = 1000
kwargs = dict(port=PORT, timeout=timeout)


def test_reload_noop(datadir, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.reload(**kwargs, appdir=Path())
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1
    assert len(ret.data.devicefile.devices) == 1
    assert len(ret.data.devicefile.pipelines) == 1
    assert len(ret.data.devicefile.components) == 1


def test_reload_settings(datadir, start_tomato_daemon, stop_tomato_daemon):
    with open("settings.toml", "a") as inf:
        inf.write("example_counter.testparb = 1")
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1
    assert len(ret.data.devicefile.devices) == 1
    assert len(ret.data.devicefile.pipelines) == 1
    assert len(ret.data.devicefile.components) == 1
    assert ret.data.settings["drivers"]["example_counter"]["testparb"] == 1
    assert ret.data.devicefile.drivers["example_counter"].settings["testparb"] == 1


def test_reload_cmps_pips(datadir, start_tomato_daemon, stop_tomato_daemon):
    with open("devices_counter.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1
    assert len(ret.data.devicefile.devices) == 1
    assert len(ret.data.devicefile.pipelines) == 4
    assert len(ret.data.devicefile.components) == 4


def test_reload_devs(datadir, start_tomato_daemon, stop_tomato_daemon):
    with open("devices_multidev.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1
    assert len(ret.data.devicefile.devices) == 2
    assert len(ret.data.devicefile.pipelines) == 2
    assert len(ret.data.devicefile.components) == 3


def test_reload_drvs(datadir, start_tomato_daemon, stop_tomato_daemon):
    # Let's add psutil driver / device
    with open("devices_psutil.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 2
    assert len(ret.data.devicefile.devices) == 2
    assert len(ret.data.devicefile.pipelines) == 1
    assert len(ret.data.devicefile.components) == 2
    assert utils.wait_until_tomato_running(port=PORT, timeout=timeout)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    ret = tomato.status(**kwargs, appdir=Path())
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 2

    # Let's remove psutil driver / device and modify channels
    with open("devices_counter.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)

    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1
    assert len(ret.data.devicefile.devices) == 1
    assert len(ret.data.devicefile.pipelines) == 4
    assert len(ret.data.devicefile.components) == 4
    assert utils.wait_until_tomato_running(port=PORT, timeout=timeout)

    ret = tomato.status(**kwargs, appdir=Path())
    assert ret.success
    assert ret.data is not None
    assert len(ret.data.devicefile.drivers) == 1


def test_reload_running(datadir, start_tomato_daemon, stop_tomato_daemon):
    utils.run_casenames(["counter_20_5"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)

    # Try modifying settings of a driver in use
    with open("settings.toml", "a") as inf:
        inf.write("example_counter.testparb = 1")
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
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
    assert ret.msg is not None
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try removing channel on device
    with open("devices_reload_channel.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try modifying address on device
    with open("devices_reload_address.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
    assert "reload would modify components of a running pipeline" in ret.msg

    # Try removing pipeline
    with open("devices_reload_pipdel.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
    assert "reload would delete a running pipeline" in ret.msg

    # Try modifying pipeline
    with open("devices_reload_pipmod.json", "r") as inf:
        jsdata = json.load(inf)
    with open("devices.yml", "w") as ouf:
        yaml.dump(jsdata, ouf)
    ret = tomato.reload(**kwargs, appdir=Path())
    print(f"{ret=}")
    assert ret.success is False
    assert ret.msg is not None
    assert "reload would modify components of a running pipeline" in ret.msg
