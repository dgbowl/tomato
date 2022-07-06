import subprocess
import time
import psutil
import signal
import os


def run_casename(casename: str, jobname: str = None, inter_func: callable = None) -> str:
    cfg = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(["tomato", "-t", "-vv"], creationflags=cfg)
    p = psutil.Process(pid=proc.pid)
    while not os.path.exists("database.db"):
        time.sleep(0.1)
    subprocess.run(["ketchup", "-t", "load", casename, "dummy-10", "-vv"])
    args = ["ketchup", "-t", "submit", f"{casename}.yml", "dummy-10", "-vv"]
    if jobname is not None:
        args.append("--jobname")
        args.append(jobname)
    print(args)
    subprocess.run(args)
    subprocess.run(["ketchup", "-t", "ready", "dummy-10", "-vv"])

    if inter_func:
        inter_func()

    while True:
        ret = subprocess.run(
            ["ketchup", "-t", "status", "1"],
            capture_output=True,
            text=True,
        )
        end = False
        for line in ret.stdout.split("\n"):
            if line.startswith("status"):
                status = line.split("=")[1].strip()
                if status.startswith("c"):
                    end = True
                    break
                else:
                    time.sleep(0.1)
        if end:
            break

    for cp in p.children():
        cp.send_signal(signal.SIGTERM)
    proc.terminate()
    return status

def kill_job():
    print('Sleeping 2 seconds...')
    time.sleep(2)
    subprocess.run(["ketchup", "-t", "cancel", "1", "-vv"])