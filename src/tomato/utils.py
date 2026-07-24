import os
import subprocess
from logging import Logger
from pathlib import Path

import psutil
import yaml
import zmq

context = zmq.Context()


def spawn_cmd(cmd: list[str], logger: Logger) -> None:
    logger.debug("starting %s", cmd[0])
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NO_WINDOW
        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)


def load_device_file(yamlpath: Path, logger: Logger) -> dict:
    logger.debug("loading device file from '%s'", yamlpath)
    try:
        with yamlpath.open("r") as infile:
            jsdata = yaml.safe_load(infile)
    except FileNotFoundError:
        raise RuntimeError("Device file not found. Did you run 'tomato init'?")
    return jsdata


def get_pid() -> int:
    if psutil.WINDOWS:
        pid = os.getpid()
        thispid = os.getpid()
        thisproc = psutil.Process(thispid)
        for p in thisproc.parents():
            if p.name() == "tomato-driver.exe":
                pid = p.pid
                break
    elif psutil.POSIX:
        pid = os.getpid()
    return pid
