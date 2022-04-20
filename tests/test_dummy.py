import pytest
import json
import os
import subprocess
import time
import signal

@pytest.mark.parametrize(
    "casename, npoints",
    [
        (   
            "dummy_random_20_1", 
            20,
        ),
        (   
            "dummy_random_5_2", 
            3,
        ),
    ],
)
def test_run_dummy_random(casename, npoints, datadir):
    os.chdir(datadir)
    t = subprocess.Popen(
        ["tomato", "-t", "-vv"], 
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    time.sleep(1)
    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])
    
    while True:
        ret = subprocess.run(
            ["ketchup", "-t", "status", "1"], capture_output=True, text=True
        )
        status = ret.stdout.split("\n")[1].split(":")[1].strip().replace("'","")
        if status.startswith("c"):
            break
        else:
            time.sleep(1)
    
    os.kill(t.pid, signal.SIGTERM)
    
    assert status == "c"
    files = os.listdir(os.path.join(".", "Jobs", "1"))
    assert "jobdata.json" in files
    assert "jobdata.log" in files
    data = []
    for file in files:
        if file.endswith("_data.json"):
            with open(os.path.join(".", "Jobs", "1", file), "r") as of:
                jsdata = json.load(of)
                for point in jsdata["data"]:
                    data.append(point)
    assert len(data) == npoints