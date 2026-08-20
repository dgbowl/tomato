import os
import random
import subprocess
import time

import tomato

from . import utils

PORT = 12345
TIME = 1000
kwargs = {"port": PORT, "timeout": TIME}
NAME = "example_counter:example-addr:1"


def test_passata_api_status(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.status(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert "running" in ret.data


def test_passata_api_attrs(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.attrs(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert "max" in ret.data


def test_passata_api_capabs(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.capabilities(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert "count" in ret.data


def test_passata_api_get_attrs(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.get_attrs(
        name=NAME,
        attrs=["max", "min"],
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert "max" in ret.data
    assert "min" in ret.data


def test_passata_api_set_attr(start_tomato_daemon, stop_tomato_daemon):
    val = random.random() * 100
    ret = tomato.passata.set_attr(
        name=NAME,
        attr="max",
        val=val,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data == val
    ret = tomato.passata.get_attrs(
        name=NAME,
        attrs=["max"],
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data["max"] == val


def test_passata_api_reset(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.reset(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success


def test_passata_api_reset_force(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_60_0.1"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    time.sleep(1)  # Delay to make sure the job task on the driver is running

    ret = tomato.passata.status(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data["running"]

    ret = tomato.passata.reset(
        name=NAME,
        force=True,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success

    ret = tomato.passata.status(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data["running"] is False


def test_passata_api_constants(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.constants(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data["example_meta"] == "example string"


def test_passata_api_measure_last_data(start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.measure(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success

    ret = tomato.passata.get_last_data(
        name=NAME,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert "uts" in ret.data.coords


def test_passata_api_force(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_5_0.2"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)
    time.sleep(1)  # Delay to make sure the job task on the driver is running

    ret = tomato.passata.set_attr(
        name=NAME,
        attr="max",
        val=15,
        force=False,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success is False
    assert "running component" in ret.msg

    ret = tomato.passata.set_attr(
        name=NAME,
        attr="max",
        val=15,
        force=True,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success
    assert "set to 15.0" in ret.msg


def test_passata_cli(start_tomato_daemon, stop_tomato_daemon):
    ret = subprocess.run(
        ["passata", "status", NAME, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: component {NAME!r}" in ret.stdout

    ret = subprocess.run(
        ["passata", "attrs", NAME, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: attrs of component {NAME!r} are" in ret.stdout

    ret = subprocess.run(
        ["passata", "capabilities", NAME, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: capabilities supported by component {NAME!r} are" in ret.stdout

    ret = subprocess.run(
        ["passata", "get", NAME, "max", "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: attr 'max' of component {NAME!r} is" in ret.stdout

    ret = subprocess.run(
        ["passata", "constants", NAME, "max", "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: constants of component {NAME!r} are" in ret.stdout
