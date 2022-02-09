import logging
log = logging.getLogger(__name__)


def _get_test_magic(
    variable: str, 
    sign: str, 
    logic: str = "+", 
    active: bool = 1
) -> int:
    magic = active
    
    assert logic.lower() in {"x", "*", "and", "+", "or"}
    magic += 2 * int(logic.lower() in {"x", "*", "and"})

    assert sign.lower() in {"<", "max", ">", "min"}
    magic += 4 * int(sign.lower() in {">", "min"})

    assert variable.lower() in {"voltage", "E", "current", "I"}
    magic += 96 * int(variable.lower() in {"current", "I"})

    return magic


def _translate(technique: dict) -> dict:
    if technique["name"] == "OCV":
        tech = {
            "name": "OCV",
            "time": technique["time"],
            "record_every_dt": technique.get("record_every_dt", 60.0),
            "record_every_dE": technique.get("record_every_dE", 0.1),
        }
    elif technique["name"] == "CPLIMIT":
        tech = {
            "name": "CPLIMIT",
            "n_cycles": 1,
            "n_steps": 0,
            "current": technique["current"],
            "time": technique["time"],
            "I_range": technique["I_range"],
            "is_delta": technique.get("is_delta", False),
            "record_every_dt": technique.get("record_every_dt", 60.0),
            "record_every_dE": technique.get("record_every_dE", 0.1),
            "test1_magic": 0,
            "test1_value": 0.0,
            "test2_magic": 0,
            "test2_value": 0.0,
            "test3_magic": 0,
            "test3_value": 0.0,
            "limit_magic": 2 * int(technique.get("exit_on_limit", False)),
        }
        ci = 1
        for prop in {"voltage", "current"}:
            for cond in {"max", "min"}:
                if f"limit_{prop}_{cond}" in technique and ci < 4:
                    tech[f"test{ci}_magic"] = _get_test_magic(prop, cond)
                    tech[f"test{ci}_value"] = technique[f"limit_{prop}_{cond}"]
                    ci += 1
    elif technique["name"] == "CALIMIT":
        tech = {
            "name": "CALIMIT",
            "n_cycles": 1,
            "n_steps": 0,
            "voltage": technique["voltage"],
            "time": technique["time"],
            "is_delta": technique.get("is_delta", False),
            "record_every_dt": technique.get("record_every_dt", 60.0),
            "record_every_dE": technique.get("record_every_dE", 0.1),
            "test1_magic": 0,
            "test1_value": 0.0,
            "test2_magic": 0,
            "test2_value": 0.0,
            "test3_magic": 0,
            "test3_value": 0.0,
            "limit_magic": 2 * int(technique.get("exit_on_limit", False)),
        }
        ci = 1
        for prop in {"voltage", "current"}:
            for cond in {"max", "min"}:
                if f"limit_{prop}_{cond}" in technique and ci < 4:
                    tech[f"test{ci}_magic"] = _get_test_magic(prop, cond)
                    tech[f"test{ci}_value"] = technique[f"limit_{prop}_{cond}"]
                    ci += 1
    else:
        log.error(f"technique name '{technique['name']}' not understood.")
        tech = {
            "name": "OCV",
            "time": technique.get("time", 0.0),
            "record_every_dt": technique.get("record_every_dt", 60.0),
            "record_every_dE": technique.get("record_every_dE", 0.1),
        }
    return tech 

def payload_to_dsl(payload: list[dict]) -> list[dict]:
    translated = []
    for technique in payload:
        translated.append(_translate(technique))
    
    return translated

pl = [
    {
        "name": "OCV", "time": 3600, "record_every_dt": 10
    },
    {
        "name": "CPLIMIT", 
        "current": 0.01, 
        "time": 3600, 
        "limit_voltage_max": 4.2, 
        "I_range": "100 mA"
    },
    {
        "name": "CALIMIT", 
        "voltage": 4.2, 
        "time": 3600, 
        "limit_current_min": 0.001
    },
]