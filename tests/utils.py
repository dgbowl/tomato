import subprocess
import time
import psutil
import signal
import os


def run_casename(casename: str) -> str:
    cfg = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(["tomato", "-t", "-vv"], creationflags=cfg)
    p = psutil.Process(pid=proc.pid)
    while not os.path.exists("database.db"):
        time.sleep(0.1)
    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"])
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])

    while True:
        ret = subprocess.run(
            ["ketchup", "-t", "status", "1"],
            capture_output=True,
            text=True,
        )
        status = ret.stdout.split("\n")[1].split(":")[1].strip().replace("'", "")
        if status.startswith("c"):
            break
        else:
            time.sleep(0.1)

    for cp in p.children():
        cp.send_signal(signal.SIGTERM)
    proc.terminate()
    return status
