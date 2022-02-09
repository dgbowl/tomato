from .kbio.kbio_tech import ECC_parm

params = {
    "OCV": {
        't':  ECC_parm("Rest_time_T", float),
        'record_dt': ECC_parm("Record_every_dT", float),
        'record_dE': ECC_parm("Record_every_dE", float),
        'E_range': ECC_parm("E_Range", int),
    },
    "CPLIMIT": {
        # arrays of 20
        'I': ECC_parm("Current_step", float),
        'vs_init': ECC_parm("vs_initial", bool),
        't': ECC_parm("Duration_step", float),
        'test1_magic': ECC_parm("Test1_Config", int),
        'test1_val': ECC_parm("Test1_Value", float),
        'test2_magic': ECC_parm("Test2_Config", int),
        'test2_val': ECC_parm("Test2_Value", float),
        'test3_magic': ECC_parm("Test3_Config", int),
        'test3_val': ECC_parm("Test3_Value", float),
        'next_magic': ECC_parm("Exit_Cond", int),
        # single points
        'ns': ECC_parm("Step_number", int),
        'record_dt': ECC_parm("Record_every_dT", float),
        'record_dE': ECC_parm("Record_every_dE", float),
        'repeat': ECC_parm("N_Cycles", int),
        'I_range': ECC_parm("I_Range", int),
    },
    "CALIMIT": {
        # arrays of 20
        'E': ECC_parm("Voltage_step", float),
        'vs_init': ECC_parm("vs_initial", bool),
        't': ECC_parm("Duration_step", float),
        'test1_magic': ECC_parm("Test1_Config", int),
        'test1_val': ECC_parm("Test1_Value", float),
        'test2_magic': ECC_parm("Test2_Config", int),
        'test2_val': ECC_parm("Test2_Value", float),
        'test3_magic': ECC_parm("Test3_Config", int),
        'test3_val': ECC_parm("Test3_Value", float),
        'next_magic': ECC_parm("Exit_Cond", int),
        # single points
        'ns': ECC_parm("Step_number", int),
        'record_dt': ECC_parm("Record_every_dT", float),
        'record_dI': ECC_parm("Record_every_dI", float),
        'repeat': ECC_parm("N_Cycles", int),
    },
    "LOOP": {
        'loop': ECC_parm("loop_N_times", int),
        'goto': ECC_parm("protocol_number", int)
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