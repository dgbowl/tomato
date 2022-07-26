import subprocess
import json
import argparse
import time

def job_get_data(jobid: int) -> dict:
    subprocess.run(["ketchup", "snapshot", f"{jobid}"])
    with open(f"snapshot.{jobid}.json", "r") as inf:
        data = json.load(inf)
    return data


def job_kill(jobid: int):
    subprocess.run(["ketchup", "cancel", f"{jobid}"])


def decide_continue(data: dict) -> bool:
    tsteps = data["steps"][0]["data"]
    checksum = sum([ts["raw"]["value"]["n"] for ts in tsteps])
    
    if checksum > 20:
        return False
    else:
        return True

def job_get_jobid(jobname: str) -> int:
    return 1


def parse_args():
    parser = argparse.ArgumentParser
    parser.add_argument(
        "-d",
        "--delay",
        type=int,
        default=60,
        help="Delay between monitoring checks",
    )
    parser.add_argument(
        "jobname",
        help="Job name of the job to be monitored",
    )
    args = parser.parse_args()
    return args.jobname, args.delay


def main():
    jobname, delay = parse_args()
    jobid = job_get_jobid(jobname)

    while True:
        tstart = time.perf_counter()
        data = job_get_data(jobid)
        cont = decide_continue(data)
        if cont:
            while time.perf_counter() - tstart < delay:
                time.sleep(0.1)
        else:
            job_kill(jobid)
            break


if __name__ == "__main__":
    main()

