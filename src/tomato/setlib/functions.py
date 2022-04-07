import os
import textwrap
import toml
import logging
import appdirs
from importlib import metadata
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_VERSION = metadata.version("tomato")


def get_dirs() -> appdirs.AppDirs:
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
            
            [samples]
            path = '{os.path.join(configpath, 'samples.yml')}'

            [devices]
            path = '{os.path.join(configpath, 'devices.toml')}'

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


def get_pipelines(tomlpath: str) -> dict:
    log.debug(f"loading pipeline settings from '{tomlpath}'")
    settings = toml.load(tomlpath)
    ppls = {}
    for k, v in settings["pipelines"].items():
        for devname in v["add_device"].keys():
            if v["add_device"][devname]["channel"] == "each":
                chs = settings["devices"][devname]["channels"]
            else:
                chs = [v["add_device"][devname]["channel"]]
            for ch in chs:
                name = k + str(ch)
                dpars = settings["devices"][devname]
                data = {k: v for k, v in dpars.items() if k is not "channels"}
                data["channel"] = ch
                ppls[name] = {v["add_device"][devname]["name"]: data}
    return ppls
