
_device_to_parser = {
    "dummy": "dummy",
    "biologic": "electrochem",
}

def get_yadg_preset(method: list[dict], pipeline: dict) -> dict:
    preset = {
        "metadata": {
            "version": "4.1.1",
            "provenance": {
                "type": "tomato"
            },
            "timezone": "localtime"
        },
        "steps": []
    }

    devices = {item["tag"]: item["driver"] for item in pipeline["devices"]}
    for dev in set([item["device"] for item in method]):
        step = {
            "tag": dev,
            "parser": _device_to_parser[devices[dev]],
            "input": {
                "folders": ["."],
                "prefix": dev,
                "suffix": "data.json"
            },
            "parameters": {
                "filetype": "tomato.json"
            }
        }
        preset["steps"].append(step)
    return preset
        
