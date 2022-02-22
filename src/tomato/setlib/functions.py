import os
import textwrap
import toml
import logging
from importlib import metadata
from datetime import datetime, timezone

log = logging.getLogger(__name__)

def get_settings(configpath: str, datapath: str) -> dict:
    settingsfile = os.path.join(configpath, "settings.toml")
    if not os.path.exists(settingsfile):
        log.warning(f"config file not present. Writing defaults to '{settingsfile}'")
        defaults = textwrap.dedent(f"""\
            # Default settings for tomato v{metadata.version('tomato')}
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
            """)
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
                data = {
                    "address": settings["devices"][devname]["address"],
                    "driver": settings["devices"][devname]["driver"],
                    "channel": ch,
                    "capabilities": settings["devices"][devname]["capabilities"]
                }
                ppls[name] = {v["add_device"][devname]["name"]: data}
    return ppls