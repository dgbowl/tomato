from .kbio.kbio_tech import ECC_parm
from dataclasses import dataclass

named_params = {
    'time': ECC_parm("Rest_time_T", float),
    'record_every_dt': ECC_parm("Record_every_dT", float),
    'record_every_dE': ECC_parm("Record_every_dE", float),
    'E_range': ECC_parm("E_Range", int),
    'I_range': ECC_parm("I_Range", int),
    'current': ECC_parm("Current_step", float),
    'voltage': ECC_parm("Voltage_step", float),
    'is_delta': ECC_parm("vs_initial", bool),
    'test1_magic': ECC_parm("Test1_Config", int),
    'test1_value': ECC_parm("Test1_Value", float),
    'test2_magic': ECC_parm("Test2_Config", int),
    'test2_value': ECC_parm("Test2_Value", float),
    'test3_magic': ECC_parm("Test3_Config", int),
    'test3_value': ECC_parm("Test3_Value", float),
    'limit_magic': ECC_parm("Exit_Cond", int),
    'n_cycles': ECC_parm("N_Cycles", int),
    'n_steps': ECC_parm("Step_number", int),
    'n_gotos': ECC_parm("loop_N_times", int),
    'goto': ECC_parm("protocol_number", int)
}

params = {
    "OCV": {
        'time': 1,
        'record_every_dE': 1,
        'record_every_dt': 1,
        'E_range': 1
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

@dataclass
class cplimit_step:
    current: float
    is_delta: bool
    time: float
    test1_magic: int
    test1_value: float
    test2_magic: int
    test2_value: float
    test3_magic: int
    test3_value: float
    limit_magic: int

@dataclass
class calimit_step:
    voltage: float
    is_delta: bool
    time: float
    test1_magic: int
    test1_value: float
    test2_magic: int
    test2_value: float
    test3_magic: int
    test3_value: float
    limit_magic: int