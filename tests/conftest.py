import logging
import os
import shutil
import subprocess

import pytest

from . import utils

logger = logging.getLogger(__name__)


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
    ret = subprocess.run(
        ["tomato", "init", "-p", f"{port}", "-A", ".", "-D", ".", "-L", "."],
        check=True,
    )
    logger.debug(f"{ret=}")
    ret = subprocess.run(
        ["tomato", "start", "-p", f"{port}", "-A", ".", "-vv"],
        check=True,
    )
    logger.debug(f"{ret=}")
    assert utils.wait_until_tomato_running(port=port, timeout=3)
    assert utils.wait_until_tomato_drivers(port=port, timeout=3)
    assert utils.wait_until_tomato_components(port=port, timeout=5)
    yield


@pytest.fixture(scope="function")
def stop_tomato_daemon(port: int = 12345):
    yield
    # teardown_stuff
    ret = subprocess.run(
        ["tomato", "stop", "-p", f"{port}"],
        check=True,
    )
    logger.debug(f"{ret=}")


@pytest.fixture(autouse=True, scope="function")
def prepare_test():
    utils.kill_tomato_procs()
    yield
