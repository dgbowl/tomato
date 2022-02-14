import os
from typing import Union

import logging
log = logging.getLogger(__name__)

from .kbio.kbio_api import KBIO_api
from .kbio.kbio_types import PROG_STATE, VMP3_FAMILY, EccParams
from .kbio.tech_types import TECH_ID
from .kbio.kbio_tech import make_ecc_parm, make_ecc_parms, ECC_parm
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


def get_num_steps(tech: dict) -> int:
    ns = 1
    for k in {
        "current", 
        "voltage", 
        "is_delta", 
        "time", 
        "limit_voltage_min", 
        "limit_voltage_max",
        "limit_current_min", 
        "limit_current_max", 
    }:
        if k in tech and isinstance(tech[k], list):
            ns = max(len(tech[k]), ns)
    return ns


def pad_steps(param: Union[list, int, float], ns: int) -> list:
    if isinstance(param, list):
        ret = [0] * ns
        for i in range(ns):
            ret[i] = param[i]
    else:
        ret = [param] * ns
    return ret
        

def translate(technique: dict) -> dict:
    if technique["name"] == "OCV":
        tech = {
            "name": "OCV",
            "Rest_time_T": technique["time"],
            "Record_every_dT": technique.get("record_every_dt", 30.0),
            "Record_every_dE": technique.get("record_every_dE", 0.005),
        }
    elif technique["name"] in {"CPLIMIT", "CALIMIT"}:
        ns = get_num_steps(technique)
        tech = {
            "name": technique["name"],
            "Step_number": ns - 1,
            "N_Cycles": technique.get("n_cycles", 1),
            "I_range": technique["I_range"],
            "Duration_step": pad_steps(technique["time"], ns),
            "vs_initial": pad_steps(technique.get("is_delta", False), ns),
            "Record_every_dT": pad_steps(technique.get("record_every_dt", 30.0), ns),
            "Record_every_dE": pad_steps(technique.get("record_every_dE", 0.005), ns),
            "Test1_Config": pad_steps(0, ns),
            "Test1_Value": pad_steps(0.0, ns),
            "Test2_Config": pad_steps(0, ns),
            "Test2_Value": pad_steps(0.0, ns),
            "Test3_Config": pad_steps(0, ns),
            "Test3_Value": pad_steps(0.0, ns),
            "Exit_Cond": pad_steps(2 * int(technique.get("exit_on_limit", False)), ns),
        }
        ci = 1
        for prop in {"voltage", "current"}:
            for cond in {"max", "min"}:
                if f"limit_{prop}_{cond}" in technique and ci < 4:
                    conf = get_test_magic(prop, cond)
                    val = technique[f"limit_{prop}_{cond}"]
                    tech[f"Test{ci}_Config"] = pad_steps(conf, ns)
                    tech[f"Test{ci}_Value"] = pad_steps(val, ns)
                    ci += 1
        if technique["name"] == "CPLIMIT":
            tech["Current_step"] = pad_steps(technique["current"], ns),
        elif technique["name"] == "CALIMIT":
            tech["Voltage_step"] = pad_steps(technique["current"], ns),
    else:
        log.error(f"technique name '{technique['name']}' not understood.")
        tech = {
            "name": "OCV",
            "time": technique.get("time", 0.0),
            "record_every_dt": technique.get("record_every_dt", 60.0),
            "record_every_dE": technique.get("record_every_dE", 0.1),
        }
    return tech 


def dsl_to_ecc(api, dsl: dict) -> EccParams:
    eccs = []
    for k, val in dsl.items():
        if isinstance(val, list):
            for i, v in zip(range(len(val)), val):
                ecc = make_ecc_parm(api, ECC_parm(k, named_params[k]), v, i)
                eccs.append(ecc)
        else:
            ecc = make_ecc_parm(api, ECC_parm(k, named_params[k]), v)
            eccs.append(ecc)
    eccpars = make_ecc_parms(api, *eccs)
    return eccpars


def payload_to_ecc(api, payload: list[dict]) -> list[dict]:
    eccs = []
    for technique in payload:
        dsl = translate(technique)
        eccpars = dsl_to_ecc(api, dsl)
        eccs.append((dsl["name"], eccpars))
    return eccs


def parse_raw_data(api, data, devname):
    current_values, data_info, data_record = data

    status = PROG_STATE(current_values.State).name
    techname = TECH_ID(data_info.TechniqueID).name
    vmp3 = devname in VMP3_FAMILY

    dtypes = datatypes["VMP3" if vmp3 else "SP-300"][techname]
    
    parsed_data = []
    ix = 0
    for _ in range(data_info.NbRows):
        inx = ix + data_info.NbCols
        point = {}
        t_rel = 0
        for k, v in zip(dtypes, data_record[ix:inx]):
            if k == "t_low":
                t_rel += v
            elif k == "t_high":
                t_rel += v << 32
            else:
                point[k] = api.ConvertNumericIntoSingle(v)
        point["time"] = t_rel * current_values.TimeBase
        parsed_data.append(point)
        ix = inx
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
