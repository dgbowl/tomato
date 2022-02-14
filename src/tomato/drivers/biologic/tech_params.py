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

params = {
    "OCV": {
        'wait': 1,
        'record_every_dE': 1,
        'record_every_dt': 1,
    },
    "CPLIMIT": {
        'current': 20,
        'is_delta': 20,
        'time': 20,
        'test1_magic': 20,
        'test1_value': 20,
        'test2_magic': 20,
        'test2_value': 20,
        'test3_magic': 20,
        'test3_value': 20,
        'limit_magic': 20,
        'n_cycles': 1,
        'n_steps': 1,
        'record_every_dt': 1,
        'record_every_dE': 1,
        'I_range': 1,
    },
    "CALIMIT": {
        'voltage': 20,
        'is_delta': 20,
        'time': 20,
        'test1_magic': 20,
        'test1_value': 20,
        'test2_magic': 20,
        'test2_value': 20,
        'test3_magic': 20,
        'test3_value': 20,
        'limit_magic': 20,
        'n_cycles': 1,
        'n_steps': 1,
        'record_every_dt': 1,
        'record_every_dE': 1,
        'I_range': 1,
    },
    "LOOP": {
        'n_gotos': 1,
        'goto': 1
    }
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
        "CALIMIT": "cplimit.ecc",
        "LOOP": "loop.ecc"
    },
    "SP-300": {
        "OCV": "ocv4.ecc",
        "CPLIMIT": "cplimit4.ecc",
        "CALIMIT": "calimit4.ecc",
        "LOOP": "loop4.ecc"
    }
}
