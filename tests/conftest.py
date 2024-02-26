from setuptools import distutils
import os
import pytest
import subprocess
import psutil


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
        distutils.dir_util.copy_tree(test_dir, str(tmpdir))
    base_dir, _ = os.path.split(test_dir)
    common_dir = os.path.join(base_dir, "common")
    if os.path.isdir(common_dir):
        distutils.dir_util.copy_tree(common_dir, str(tmpdir))
    print(f"{tmpdir=}")
    return tmpdir


@pytest.fixture(scope="function")
def start_tomato_daemon(tmpdir: str, port: int = 12345):
    # setup_stuff
    os.chdir(tmpdir)
    subprocess.run(["tomato", "init", "-p", f"{port}", "-A", ".", "-D", "."])
    subprocess.run(["tomato", "start", "-p", f"{port}", "-A", ".", "-L", "."])
    yield
    # teardown_stuff


@pytest.fixture(scope="function")
def stop_tomato_daemon(port: int = 12345):
    # setup_stuff
    yield
    # teardown_stuff
    print("stop_tomato_daemon")
    subprocess.run(["tomato", "stop", "-P", f"12345"])
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
    gone, alive = psutil.wait_procs(procs, timeout=5)
    print(f"{gone=}")
    print(f"{alive=}")
