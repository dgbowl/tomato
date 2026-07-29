import os
import shutil
import subprocess

import psutil
import pytest

from . import utils


@pytest.fixture
def datadir(tmpdir, request):
    """
    from: https://stackoverflow.com/a/29631801
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    if os.path.isdir(test_dir):
        shutil.copytree(test_dir, str(tmpdir), dirs_exist_ok=True)
    base_dir, _ = os.path.split(test_dir)
    common_dir = os.path.join(base_dir, "common")
    if os.path.isdir(common_dir):
        shutil.copytree(common_dir, str(tmpdir), dirs_exist_ok=True)
    print(f"{tmpdir=}")
    return tmpdir


@pytest.fixture(scope="function")
def start_tomato_daemon(tmpdir: str, port: int = 12345):
    # setup_stuff
    os.chdir(tmpdir)
    subprocess.run(
        ["tomato", "init", "-p", f"{port}", "-A", ".", "-D", ".", "-L", "."],
        check=True,
    )
    subprocess.run(
        ["tomato", "start", "-p", f"{port}", "-A", ".", "-vv"],
        check=True,
    )
    assert utils.wait_until_tomato_running(port=port, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=port, timeout=3000)
    assert utils.wait_until_tomato_components(port=port, timeout=5000)
    yield
    # teardown_stuff


@pytest.fixture(scope="function")
def stop_tomato_daemon(port: int = 12345):
    # setup_stuff
    yield
    # teardown_stuff
    print("stop_tomato_daemon")
    subprocess.run(["tomato", "stop", "-p", f"{port}"], check=True)
    if psutil.WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-daemon.exe"], check=True)
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-job.exe"], check=True)
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-driver.exe"], check=True)
    else:
        subprocess.run(["killall", "tomato-daemon"], check=True)
        subprocess.run(["killall", "tomato-job"], check=True)
        subprocess.run(["killall", "tomato-driver"], check=True)

    procs = []
    for p in psutil.process_iter(["name"]):
        for name in ["tomato-daemon", "tomato-job", "tomato-driver"]:
            if name in p.info["name"]:
                try:
                    pc = p.children()
                    pc.append(p)
                    procs += pc
                    pc[-1].terminate()
                except psutil.NoSuchProcess:
                    pass
    psutil.wait_procs(procs, timeout=1)
