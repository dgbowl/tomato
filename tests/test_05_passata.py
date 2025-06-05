import zmq
import random
import subprocess
import os
from . import utils
import tomato

PORT = 12345
TIME = 1000
CTXT = zmq.Context()
kwargs = dict(port=PORT, timeout=TIME, context=CTXT)


def test_passata_api_status(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.status(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert "running" in ret.data


def test_passata_api_attrs(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.attrs(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert "max" in ret.data


def test_passata_api_capabs(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.capabilities(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert "count" in ret.data


def test_passata_api_get_attrs(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.get_attrs(
        name="example_counter:(example-addr,1)",
        attrs=["max", "min"],
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert "max" in ret.data
    assert "min" in ret.data


def test_passata_api_set_attr(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    val = random.random() * 100
    ret = tomato.passata.set_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        val=val,
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data == val
    ret = tomato.passata.get_attrs(
        name="example_counter:(example-addr,1)",
        attrs=["max"],
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data["max"] == val


def test_passata_api_reset(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.reset(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success


def test_passata_api_reset_force(datadir, start_tomato_daemon, stop_tomato_daemon):
    os.chdir(datadir)
    utils.run_casenames(["counter_60_0.1"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=1e4)
    ret = tomato.passata.status(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data["running"] is True

    ret = tomato.passata.reset(
        name="example_counter:(example-addr,1)",
        force=True,
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success

    ret = tomato.passata.status(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data["running"] is False


def test_passata_api_constants(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.constants(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert ret.data["example_meta"] == "example string"


def test_passata_api_last_data(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.get_last_data(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(f"{ret=}")
    assert ret.success
    assert "uts" in ret.data.coords


def test_passata_api_measure(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = tomato.passata.measure(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    assert ret.success


def test_passata_api_force(datadir, start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    utils.run_casenames(["counter_5_0.2"], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(jobid=1, status="r", port=PORT, timeout=5000)

    ret = tomato.passata.set_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        val=15,
        force=False,
        **kwargs,
    )
    assert ret.success is False
    assert "running component" in ret.msg

    ret = tomato.passata.set_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        val=15,
        force=True,
        **kwargs,
    )
    assert ret.success
    assert "set to 15.0" in ret.msg


def test_passata_cli(start_tomato_daemon, stop_tomato_daemon):
    utils.wait_until_tomato_running(port=PORT, timeout=1000)
    utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    utils.wait_until_tomato_components(port=PORT, timeout=5000)
    ret = subprocess.run(
        [
            "passata",
            "status",
            "example_counter:(example-addr,1)",
            "-p",
            f"{PORT}",
        ],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert "Success: component ('example-addr', '1')" in ret.stdout

    ret = subprocess.run(
        [
            "passata",
            "attrs",
            "example_counter:(example-addr,1)",
            "-p",
            f"{PORT}",
        ],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert "Success: attrs of component ('example-addr', '1') are" in ret.stdout

    ret = subprocess.run(
        [
            "passata",
            "capabilities",
            "example_counter:(example-addr,1)",
            "-p",
            f"{PORT}",
        ],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert (
        "Success: capabilities supported by component ('example-addr', '1') are"
        in ret.stdout
    )

    ret = subprocess.run(
        [
            "passata",
            "get",
            "example_counter:(example-addr,1)",
            "max",
            "-p",
            f"{PORT}",
        ],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert (
        "Success: attr 'max' of component 'example_counter:(example-addr,1)' is"
        in ret.stdout
    )

    ret = subprocess.run(
        [
            "passata",
            "constants",
            "example_counter:(example-addr,1)",
            "max",
            "-p",
            f"{PORT}",
        ],
        capture_output=True,
        text=True,
    )
    print(f"{ret=}")
    assert "Success: constants of component ('example-addr', '1') are" in ret.stdout
