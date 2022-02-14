from .kbio.kbio_tech import ECC_parm
from dataclasses import dataclass

named_params = {
    'Rest_time_T': float,
    'Duration_step': float,
    'Record_every_dT': float,
    'Record_every_dE': float,
    "E_Range": int,
    "I_Range": int,
    "Current_step": float,
    "Voltage_step": float,
    "vs_initial": bool,
    "Test1_Config": int,
    "Test1_Value": float,
    "Test2_Config": int,
    "Test2_Value": float,
    "Test3_Config": int,
    "Test3_Value": float,
    "Exit_Cond": int,
    "N_Cycles": int,
    "Step_number": int,
    "loop_N_times": int,
    "protocol_number": int
}


I_ranges = {
    "keep": -1,
    "100 pA": 0,
    "1 nA": 1,
    "10 nA": 2,
    "100 nA": 3,
    "1 μA": 4,
    "10 μA": 5,
    "100 μA": 6,
    "1 mA": 7,
    "10 mA": 8,
    "100 mA": 9,
    "1 A": 10,
    "booster": 11,
    "auto": 12,
}


E_ranges = {
    "±2.5 V": 0,
    "±5 V": 1,
    "±10 V": 2,
    "auto": 3,
}

datatypes = {
    "VMP3": {
        "OCV": ["t_high", "t_low", "Ewe", "Ece"],
        "CPLIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "CALIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "VSCANLIMIT": ["t_high", "t_low", "Ec", "<I>", "<Ewe>", "cycle"],
        "ISCANLIMIT": ["t_high", "t_low", "Ic", "<I>", "<Ewe>", "cycle"],
    },
    "SP-300": {
        "OCV": ["t_high", "t_low", "Ewe"],
        "CPLIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "CALIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "VSCANLIMIT": ["t_high", "t_low", "<I>", "<Ewe>", "cycle"],
        "ISCANLIMIT": ["t_high", "t_low", "<I>", "<Ewe>", "cycle"],
    }
}

techfiles = {
    "VMP3": {
        "OCV": "ocv.ecc",
        "CPLIMIT": "cplimit.ecc",
        "CALIMIT": "calimit.ecc",
        "LOOP": "loop.ecc"
    },
    "SP-300": {
        "OCV": "ocv4.ecc",
        "CPLIMIT": "cplimit4.ecc",
        "CALIMIT": "calimit4.ecc",
        "LOOP": "loop4.ecc"
    }
}
