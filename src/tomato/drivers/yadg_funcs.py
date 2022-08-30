from cgi import print_form
import json
import logging
import subprocess
import os

logger = logging.getLogger(__name__)

_device_to_parser = {
    "dummy": "dummy",
    "biologic": "electrochem",
}


def get_yadg_preset(method: list[dict], pipeline: dict) -> dict:
    preset = {
        "metadata": {
            "version": "4.2",
            "provenance": {"type": "tomato"},
            "timezone": "localtime",
        },
        "steps": [],
    }

    devices = {item["tag"]: item["driver"] for item in pipeline["devices"]}
    for dev in set([item["device"] for item in method]):
        step = {
            "tag": dev,
            "parser": _device_to_parser[devices[dev]],
            "input": {"folders": ["."], "prefix": dev, "suffix": "data.json"},
            "parameters": {"filetype": "tomato.json"},
            "externaldate": {
                "using": {
                    "file": {
                        "type": "json",
                        "path": f"{dev}_status.json",
                        "match": "uts",
                    }
                },
            },
        }
        preset["steps"].append(step)
    return preset


def process_yadg_preset(
    preset: dict,
    path: str,
    prefix: str,
    jobdir: str,
) -> None:
    prpath = os.path.join(path, f"preset.{prefix}.json")
    logger.debug("creating a preset file '%s'", prpath)
    with open(prpath, "w") as of:
        json.dump(preset, of)

    dgpath = os.path.join(path, f"{prefix}.json")
    logger.info("running yadg to create a datagram in '%s'", dgpath)
    command = ["yadg", "preset", "-pa", prpath, jobdir, dgpath]
    logger.debug(" ".join(command))
    subprocess.run(command, check=True)

    logger.debug("removing the preset file '%s'", prpath)
    os.unlink(prpath)
