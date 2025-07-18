import os
import pytest
import subprocess
import psutil
import shutil

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
    subprocess.run(["tomato", "init", "-p", f"{port}", "-A", ".", "-D", ".", "-L", "."])
    subprocess.run(["tomato", "start", "-p", f"{port}", "-A", ".", "-vv"])
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
    subprocess.run(["tomato", "stop", "-p", f"{port}"])
    if psutil.WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-daemon.exe"])
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-job.exe"])
        subprocess.run(["taskkill", "/F", "/T", "/IM", "tomato-driver.exe"])
    else:
        subprocess.run(["killall", "tomato-daemon"])
        subprocess.run(["killall", "tomato-job"])
        subprocess.run(["killall", "tomato-driver"])

    procs = []
    for p in psutil.process_iter(["name"]):
        for name in ["tomato-daemon", "tomato-job", "tomato-driver"]:
            if name in p.info["name"]:
                pc = p.children()
                pc.append(p)
                for proc in pc:
                    procs.append(proc)
                    try:
                        proc.terminate()
                    except psutil.NoSuchProcess:
                        pass
    gone, alive = psutil.wait_procs(procs, timeout=1)
