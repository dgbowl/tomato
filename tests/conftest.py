from setuptools import distutils
import os
import pytest
import subprocess


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
def tomato_daemon(tmpdir: str, port: int = 12345):
    # setup_stuff
    os.chdir(tmpdir)
    subprocess.run(
        ["tomato", "init", "-p", f"{port}", "--appdir", ".", "--datadir", "."]
    )
    subprocess.run(
        ["tomato", "start", "-p", f"{port}", "--appdir", ".", "--datadir", "."]
    )
    yield
    # teardown_stuff
    subprocess.run(["tomato", "stop", "-p", "12345", "--timeout", "1000"])


@pytest.fixture(autouse=True, scope="session")
def stop_tomato_daemon_session():
    # setup_stuff
    yield
    # teardown_stuff
    subprocess.run(["tomato", "stop", "-p", "12345", "--timeout", "1000"])


@pytest.fixture(scope="function")
def stop_tomato_daemon(port: int = 12345):
    # setup_stuff
    yield
    # teardown_stuff
    print(f"Running Teardown")
    subprocess.run(["tomato", "stop", "-p", f"{port}", "--timeout", "1000"])
