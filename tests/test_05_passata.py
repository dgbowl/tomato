import os
import random
import subprocess
import time

import pytest

import tomato

from . import utils

PORT = 12345
TIME = 1000
kwargs = {"port": PORT, "timeout": TIME}


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", "3.0"),
        ("example_trig:example-addr:1", "2.1"),
    ],
)
def test_passata_api_status(name, arg, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.status(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    if arg == "3.0":
        assert ret.data.state is not None
    else:
        assert ret.data.get("running") is not None


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", "max"),
        ("example_trig:example-addr:1", "points"),
    ],
)
def test_passata_api_attrs(name, arg, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.attrs(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert arg in ret.data


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", "count"),
        ("example_trig:example-addr:1", "trig_function"),
    ],
)
def test_passata_api_capabs(name, arg, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.capabilities(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert arg in ret.data


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", "max"),
        ("example_trig:example-addr:1", "points"),
    ],
)
def test_passata_api_get_attrs(name, arg, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.get_attrs(
        name=name,
        attrs=[arg],
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert arg in ret.data


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", "max"),
        ("example_trig:example-addr:1", "points"),
    ],
)
def test_passata_api_set_attr(name, arg, start_tomato_daemon, stop_tomato_daemon):
    val = random.randint(0, 10)
    ret = tomato.passata.set_attr(
        name=name,
        attr=arg,
        val=val,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data == val
    ret = tomato.passata.get_attrs(
        name=name,
        attrs=[arg],
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data[arg] == val


@pytest.mark.parametrize(
    "name",
    [
        "example_counter:example-addr:1",
        "example_trig:example-addr:1",
    ],
)
def test_passata_api_reset(name, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.reset(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success


@pytest.mark.parametrize(
    "name, case, pip",
    [
        ("example_counter:example-addr:1", "counter_60_0.1", "pip-counter"),
    ],
)
def test_passata_api_reset_force(
    name, case, pip, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([case], [None], [pip])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    time.sleep(1)  # Delay to make sure the job task on the driver is running

    ret = tomato.passata.status(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.state == "task"

    ret = tomato.passata.reset(
        name=name,
        force=True,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success

    ret = tomato.passata.status(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data.state != "task"


@pytest.mark.parametrize(
    "name, arg, val",
    [
        ("example_counter:example-addr:1", "example_meta", "example string"),
    ],
)
def test_passata_api_constants(name, arg, val, start_tomato_daemon, stop_tomato_daemon):
    ret = tomato.passata.constants(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    assert ret.data[arg] == val


@pytest.mark.parametrize(
    "name, arg",
    [
        ("example_counter:example-addr:1", ["uts"]),
        ("example_trig:example-addr:1", ["uts", "abscissa"]),
    ],
)
def test_passata_api_measure_last_data(
    name, arg, start_tomato_daemon, stop_tomato_daemon
):
    ret = tomato.passata.measure(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success

    ret = tomato.passata.get_last_data(
        name=name,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data is not None
    for coord in arg:
        assert coord in ret.data.coords


@pytest.mark.parametrize(
    "name, case, pip, attr",
    [
        ("example_counter:example-addr:1", "counter_5_0.2", "pip-counter", "max"),
    ],
)
def test_passata_api_force(
    name, case, pip, attr, datadir, start_tomato_daemon, stop_tomato_daemon
):
    os.chdir(datadir)
    utils.run_casenames([case], [None], [pip])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 5000)
    time.sleep(1)  # Delay to make sure the job task on the driver is running

    ret = tomato.passata.set_attr(
        name=name,
        attr=attr,
        val=15,
        force=False,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success is False
    assert "on a component with state 'task'" in ret.msg

    ret = tomato.passata.set_attr(
        name=name,
        attr=attr,
        val=15,
        force=True,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )
    assert ret.success
    assert "set to 15.0" in ret.msg


@pytest.mark.parametrize(
    "name, attr",
    [
        ("example_counter:example-addr:1", "max"),
        ("example_trig:example-addr:1", "points"),
    ],
)
def test_passata_cli(name, attr, start_tomato_daemon, stop_tomato_daemon):
    ret = subprocess.run(
        ["passata", "status", name, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert "Success: component" in ret.stdout

    ret = subprocess.run(
        ["passata", "attrs", name, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert "Success: attrs of component" in ret.stdout

    ret = subprocess.run(
        ["passata", "capabilities", name, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert "Success: capabilities supported by component" in ret.stdout

    ret = subprocess.run(
        ["passata", "get", name, attr, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert f"Success: attr {attr!r} of component" in ret.stdout

    ret = subprocess.run(
        ["passata", "constants", name, "-p", f"{PORT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"{ret=}")
    assert "Success: constants of component" in ret.stdout
