import os
import textwrap
import toml
import yaml
import copy
import logging
import appdirs
from importlib import metadata
from datetime import datetime, timezone
from dataclasses import dataclass

log = logging.getLogger(__name__)

_VERSION = metadata.version("tomato")


@dataclass
class LocalDir:
    user_config_dir: str
    user_data_dir: str
    user_log_dir: str


def get_dirs(testmode: bool = False) -> appdirs.AppDirs:
    if testmode:
        dirs = LocalDir(
            user_config_dir=".",
            user_data_dir=".",
            user_log_dir=".",
        )
    else:
        dirs = appdirs.AppDirs("tomato", "dgbowl", version=_VERSION)
    log.debug(f"local config folder is '{dirs.user_config_dir}'")
    log.debug(f"local data folder is '{dirs.user_data_dir}'")
    log.debug(f"local log folder is '{dirs.user_log_dir}'")
    return dirs


def get_settings(configpath: str, datapath: str) -> dict:
    settingsfile = os.path.join(configpath, "settings.toml")
    if not os.path.exists(settingsfile):
        log.warning(f"config file not present. Writing defaults to '{settingsfile}'")
        defaults = textwrap.dedent(
            f"""\
            # Default settings for tomato v{_VERSION}
            # Generated on {str(datetime.now(timezone.utc))}
            [state]
            type = 'sqlite3'
            path = '{os.path.join(datapath, 'database.db')}'

            [queue]
            type = 'sqlite3'
            path = '{os.path.join(datapath, 'database.db')}'
            storage = '{os.path.join(datapath, 'Jobs')}'

            [devices]
            path = '{os.path.join(configpath, 'devices.yml')}'

            [drivers]
            [drivers.biologic]
            dllpath = 'C:\EC-Lab Development Package\EC-Lab Development Package\'
            """
        )
        if not os.path.exists(configpath):
            os.makedirs(configpath)
        with open(settingsfile, "w") as of:
            of.write(defaults)

    log.debug(f"loading tomato settings from '{settingsfile}'")
    settings = toml.load(settingsfile)

    return settings


def _default_pipelines() -> dict[str, dict]:
    data = {
        "devices": [
            {
                "name": "dummy_device",
                "address": None,
                "channels": [5, 10],
                "driver": "dummy",
                "capabilities": ["random", "sequential"],
                "pollrate": 1,
            }
        ],
        "pipelines": [
            {
                "name": "dummy-*",
                "devices": [
                    {"tag": "worker", "name": "dummy_device", "channel": "each"}
                ],
            }
        ],
    }
    return data


def get_pipelines(yamlpath: str) -> dict:
    log.debug(f"loading pipeline settings from '{yamlpath}'")
    try:
        with open(yamlpath, "r") as infile:
            jsdata = yaml.safe_load(infile)
    except FileNotFoundError:
        log.error(f"device settings not found. Running with a 'dummy' device.")
        jsdata = _default_pipelines()
    devices = jsdata["devices"]
    pipelines = jsdata["pipelines"]
    ret = []
    for pip in pipelines:
        if "*" in pip["name"]:
            data = {"name": pip["name"], "devices": []}
            assert len(pip["devices"]) == 1
            for ppars in pip["devices"]:
                for dpars in devices:
                    if dpars["name"] == ppars["name"]:
                        break
                dev = {k: v for k, v in dpars.items() if k != "channels"}
                dev["tag"] = ppars["tag"]
                data["devices"].append(dev)
                for ch in dpars["channels"]:
                    d = copy.deepcopy(data)
                    d["devices"][0]["channel"] = ch
                    d["name"] = d["name"].replace("*", f"{ch}")
                    ret.append(d)
        else:
            data = {"name": pip["name"], "devices": []}
            for ppars in pip["devices"]:
                for dpars in devices:
                    if dpars["name"] == ppars["name"]:
                        break
                dev = {k: v for k, v in dpars.items() if k != "channels"}
                dev["tag"] = ppars["tag"]
                if isinstance(ppars.get("channel"), int):
                    assert ppars["channel"] in dpars["channels"]
                    dev["channel"] = ppars["channel"]
                else:
                    assert "*" in pip["name"]
                data["devices"].append(dev)
            ret.append(data)
    return ret
