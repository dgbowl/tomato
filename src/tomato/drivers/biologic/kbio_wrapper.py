import os

import logging
log = logging.getLogger(__name__)

from .kbio.kbio_api import KBIO_api
from .kbio.kbio_types import PROG_STATE, VMP3_FAMILY, EccParams
from .kbio.tech_types import TECH_ID
from .kbio.kbio_tech import make_ecc_parm, make_ecc_parms
from .kbio.c_utils import c_is_64b

from .tech_params import params, named_params, techfiles, datatypes

def get_test_magic(
    variable: str, 
    sign: str, 
    logic: str = "+", 
    active: bool = True
) -> int:
    magic = int(active)
    
    assert logic.lower() in {"x", "*", "and", "+", "or"}
    magic += 2 * int(logic.lower() in {"x", "*", "and"})

    assert sign.lower() in {"<", "max", ">", "min"}
    magic += 4 * int(sign.lower() in {">", "min"})

    assert variable.lower() in {"voltage", "E", "current", "I"}
    magic += 96 * int(variable.lower() in {"current", "I"})

    return magic


def translate(technique: dict) -> dict:
    if technique["name"] == "OCV":
        tech = {
            "name": "OCV",
            "wait": technique["time"],
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
                    tech[f"test{ci}_magic"] = get_test_magic(prop, cond)
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
                    tech[f"test{ci}_magic"] = get_test_magic(prop, cond)
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
        translated.append(translate(technique))
    return translated


def dsl_to_ecc(api, dsl: list[dict]) -> list[EccParams]:
    eccpars = []
    for tech in dsl:
        eccs = []
        for k, v in params[tech["name"]].items():
            print(k, v)
            if v > 1:
                ecc = make_ecc_parm(api, named_params[k], tech[k], 0)    
            else:
                ecc = make_ecc_parm(api, named_params[k], tech[k])
            eccs.append(ecc)
        print("made all pars")
        eccpar = make_ecc_parms(api, *eccs)
        eccpars.append(eccpar)
    return eccpars


def parse_raw_data(api, data, devname):
    current_values, data_info, data_record = data

    status = PROG_STATE(current_values.State).name
    techname = TECH_ID(data_info.TechniqueID).name
    vmp3 = devname in VMP3_FAMILY

    dtypes = datatypes["VMP3" if vmp3 else "SP-300"][techname]
    
    parsed_data = {}
    t_rel = 0
    for k, v in zip(dtypes, data):
        if k == "t_low":
            t_rel += v
        elif k == "t_high":
            t_rel += v << 32
        else:
            parsed_data[k] = api.ConvertNumericIntoSingle(v)
    parsed_data["time"] = t_rel * current_values.TimeBase

    return parsed_data


def get_kbio_api(dllpath):
    if c_is_64b:
        dllfile = "EClib64.dll"
    else:
        dllfile = "EClib.dll"
    apipath = os.path.join(dllpath, dllfile)
    log.debug(f"biologic library path is '{apipath}'")
    api = KBIO_api(apipath)
    return api

def get_kbio_techpath(
    dllpath, 
    techname, 
    devname,
) -> str:
    vmp3 = devname in VMP3_FAMILY
    techfile = techfiles["VMP3" if vmp3 else "SP-300"][techname]
    return os.path.join(dllpath, techfile)
