import psutil
import subprocess
import yaml

from logging import Logger
from pathlib import Path
from tomato.models import Component, Device, Pipeline


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


def get_pipelines(
    devs: dict[str, Device],
    pipelines: list,
    logger: Logger,
) -> tuple[dict[str, Pipeline], dict[str, Component]]:
    pips = {}
    cmps = {}
    for pip in pipelines:
        if "*" in pip["name"]:
            data = {"name": pip["name"], "devs": {}}
            if len(pip["devices"]) > 1:
                logger.error("more than one component in a wildcard pipeline")
                continue
            for comp in pip["devices"]:
                if comp["device"] not in devs:
                    logger.error("device '%s' not found", comp["device"])
                    break
                dev = devs[comp["device"]]
                for ch in dev.channels:
                    name = pip["name"].replace("*", f"{ch}")
                    h = f"{dev.driver}:({dev.address},{ch})"
                    c = Component(
                        name=h,
                        driver=dev.driver,
                        device=dev.name,
                        address=dev.address,
                        channel=ch,
                        role=comp["role"],
                    )
                    cmps[h] = c
                    p = Pipeline(name=name, components=[h])
                    pips[p.name] = p
        else:
            data = {"name": pip["name"], "components": []}
            for comp in pip["devices"]:
                if comp["device"] not in devs:
                    logger.error("device '%s' not found", comp["device"])
                    break
                dev = devs[comp["device"]]
                if isinstance(comp["channel"], int):
                    logger.warning(
                        "Supplying 'channel' as an int is deprecated "
                        "and will stop working in tomato-2.0."
                    )
                    comp["channel"] = str(comp["channel"])
                if comp["channel"] not in dev.channels:
                    logger.error(
                        "channel %s not found on device '%s'",
                        comp["channel"],
                        comp["device"],
                    )
                    break
                h = f"{dev.driver}:({dev.address},{comp['channel']})"
                c = Component(
                    name=h,
                    driver=dev.driver,
                    device=dev.name,
                    address=dev.address,
                    channel=comp["channel"],
                    role=comp["role"],
                )
                data["components"].append(h)
                cmps[h] = c
            pips[data["name"]] = Pipeline(**data)
    return pips, cmps
