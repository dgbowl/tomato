named_params = {
    "Rest_time_T": float,
    "Duration_step": float,
    "Record_every_dT": float,
    "Record_every_dE": float,
    "Record_every_dI": float,
    "E_Range": int,
    "I_Range": int,
    "Current_step": float,
    "Voltage_step": float,
    "Scan_Rate": float,
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
    "Scan_number": int,
    "loop_N_times": int,
    "protocol_number": int,
    "Begin_measuring_I": float,
    "End_measuring_I": float,
    "Begin_measuring_E": float,
    "End_measuring_E": float,
}


I_ranges = {
    "keep": -1,
    "100 pA": 0,
    "1 nA": 1,
    "10 nA": 2,
    "100 nA": 3,
    "1 uA": 4,
    "10 uA": 5,
    "100 uA": 6,
    "1 mA": 7,
    "10 mA": 8,
    "100 mA": 9,
    "1 A": 10,
    "booster": 11,
    "auto": 12,
}


E_ranges = {
    "+-2.5 V": 0,
    "+-5.0 V": 1,
    "+-10 V": 2,
    "auto": 3,
}

datatypes = {
    "VMP3": {
        "OCV": ["t_high", "t_low", "Ewe", "Ece"],
        "CPLIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "CALIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "PDYNLIMIT": ["t_high", "t_low", "Ec", "<I>", "<Ewe>", "cycle"],
        "GDYNLIMIT": ["t_high", "t_low", "Ic", "<I>", "<Ewe>", "cycle"],
    },
    "SP-300": {
        "OCV": ["t_high", "t_low", "Ewe"],
        "CPLIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "CALIMIT": ["t_high", "t_low", "Ewe", "I", "cycle"],
        "PDYNLIMIT": ["t_high", "t_low", "<I>", "<Ewe>", "cycle"],
        "GDYNLIMIT": ["t_high", "t_low", "<I>", "<Ewe>", "cycle"],
    },
}

techfiles = {
    "VMP3": {
        "open_circuit_voltage": "ocv.ecc",
        "constant_current": "cplimit.ecc",
        "constant_voltage": "calimit.ecc",
        "sweep_voltage": "vscanlimit.ecc",
        "sweep_current": "iscanlimit.ecc",
        "loop": "loop.ecc",
    },
    "SP-300": {
        "open_circuit_voltage": "ocv4.ecc",
        "constant_current": "cplimit4.ecc",
        "constant_voltage": "calimit4.ecc",
        "sweep_voltage": "vscanlimit4.ecc",
        "sweep_current": "iscanlimit4.ecc",
        "loop": "loop4.ecc",
    },
}
