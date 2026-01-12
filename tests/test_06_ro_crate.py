import os
import pytest
import subprocess
from tomato.daemon.crates import to_rocrate
from . import utils

try:
    from rocrate.rocrate import ROCrate

    _has_rocrate = True
except ImportError:
    _has_rocrate = False


PORT = 12345


@pytest.mark.skipif(not _has_rocrate, reason="requires rocrate")
@pytest.mark.parametrize(
    "datapath, make_child",
    [
        ("results.ref.nc", False),
        ("results.ref.nc", True),
    ],
)
def test_to_rocrate(datapath, make_child, datadir):
    os.chdir(datadir)
    userid = "userid"
    sampleid = "sampleid"
    to_rocrate(datapath, userid, sampleid, make_child)
    cratepath = f"{datapath[:-3]}.zip"

    assert os.path.exists(cratepath)

    crate = ROCrate(cratepath)
    assert crate.get(userid) is not None
    assert crate.get(sampleid) is not None
    assert crate.get(datapath) is not None
    objs = sum([1 if e.type == "RepositoryObject" else 0 for e in crate.get_entities()])
    if make_child:
        assert objs == 2
    else:
        assert objs == 1


@pytest.mark.skipif(not _has_rocrate, reason="requires rocrate")
@pytest.mark.parametrize(
    "casename, par",
    [
        ("rocrate_1_0.1", False),
    ],
)
def test_job_rocrate(casename, par, datadir, tmpdir, stop_tomato_daemon):
    os.chdir(tmpdir)
    subprocess.run(["tomato", "init", "-p", f"{PORT}", "-A", ".", "-D", ".", "-L", "."])
    with open("settings.toml", "r") as inp:
        settings = inp.read().replace("# default", "default")
    with open("settings.toml", "w") as out:
        out.write(settings)

    subprocess.run(["tomato", "start", "-p", f"{PORT}", "-A", ".", "-vv"])
    assert utils.wait_until_tomato_running(port=PORT, timeout=1000)
    assert utils.wait_until_tomato_drivers(port=PORT, timeout=3000)
    assert utils.wait_until_tomato_components(port=PORT, timeout=5000)

    os.chdir(datadir)
    utils.run_casenames([casename], [None], ["pip-counter"])
    assert utils.wait_until_ketchup_status(1, "r", PORT, 10000)
    assert utils.wait_until_ketchup_status(1, "c", PORT, 20000)

    assert os.path.exists("results.1.zip")
    crate = ROCrate("results.1.zip")
    assert crate.get("user.identifier") is not None
    assert crate.get("rocrate_1_0.1") is not None
    assert crate.get("results.1.nc") is not None
