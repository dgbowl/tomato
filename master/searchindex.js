Search.setIndex({docnames:["apidoc/tomato","apidoc/tomato.daemon","apidoc/tomato.dbhandler","apidoc/tomato.drivers","apidoc/tomato.drivers.biologic","apidoc/tomato.drivers.biologic.kbio","apidoc/tomato.drivers.dummy","apidoc/tomato.ketchup","apidoc/tomato.setlib","index","installation","quickstart","usage","version"],envversion:{"sphinx.domains.c":2,"sphinx.domains.changeset":1,"sphinx.domains.citation":1,"sphinx.domains.cpp":5,"sphinx.domains.index":1,"sphinx.domains.javascript":2,"sphinx.domains.math":2,"sphinx.domains.python":3,"sphinx.domains.rst":2,"sphinx.domains.std":2,"sphinx.ext.intersphinx":1,sphinx:56},filenames:["apidoc\\tomato.rst","apidoc\\tomato.daemon.rst","apidoc\\tomato.dbhandler.rst","apidoc\\tomato.drivers.rst","apidoc\\tomato.drivers.biologic.rst","apidoc\\tomato.drivers.biologic.kbio.rst","apidoc\\tomato.drivers.dummy.rst","apidoc\\tomato.ketchup.rst","apidoc\\tomato.setlib.rst","index.rst","installation.rst","quickstart.rst","usage.rst","version.rst"],objects:{"":[[0,3,0,"-","tomato"]],"dgbowl_schemas.tomato.payload_0_2":[[11,0,1,"","Payload"]],"dgbowl_schemas.tomato.payload_0_2.Payload":[[11,1,1,"","extract_methodfile"],[11,1,1,"","extract_samplefile"],[11,2,1,"","method"],[11,2,1,"","sample"],[11,2,1,"","tomato"],[11,2,1,"","version"]],"tomato.daemon":[[1,3,0,"-","main"]],"tomato.daemon.main":[[1,4,1,"","main_loop"]],"tomato.dbhandler":[[2,3,0,"-","sqlite"]],"tomato.dbhandler.sqlite":[[2,4,1,"","get_db_conn"],[2,4,1,"","job_get_all"],[2,4,1,"","job_get_all_queued"],[2,4,1,"","job_get_info"],[2,4,1,"","job_set_status"],[2,4,1,"","job_set_time"],[2,4,1,"","pipeline_assign_job"],[2,4,1,"","pipeline_eject_sample"],[2,4,1,"","pipeline_get_all"],[2,4,1,"","pipeline_get_info"],[2,4,1,"","pipeline_get_running"],[2,4,1,"","pipeline_insert"],[2,4,1,"","pipeline_load_sample"],[2,4,1,"","pipeline_remove"],[2,4,1,"","pipeline_reset_job"],[2,4,1,"","queue_payload"],[2,4,1,"","queue_setup"],[2,4,1,"","state_setup"]],"tomato.drivers":[[4,3,0,"-","biologic"],[3,3,0,"-","driver_funcs"],[6,3,0,"-","dummy"],[3,3,0,"-","logger_funcs"],[3,3,0,"-","yadg_funcs"]],"tomato.drivers.biologic":[[5,3,0,"-","kbio"],[4,3,0,"-","kbio_wrapper"],[4,3,0,"-","main"],[4,3,0,"-","tech_params"]],"tomato.drivers.biologic.kbio":[[5,3,0,"-","c_utils"],[5,3,0,"-","kbio_api"],[5,3,0,"-","kbio_tech"],[5,3,0,"-","kbio_types"],[5,3,0,"-","tech_types"],[5,3,0,"-","utils"]],"tomato.drivers.biologic.kbio.c_utils":[[5,5,1,"","POD"],[5,5,1,"","c_buffer"],[5,4,1,"","c_dump"]],"tomato.drivers.biologic.kbio.c_utils.POD":[[5,6,1,"","keys"],[5,7,1,"","subset"]],"tomato.drivers.biologic.kbio.c_utils.c_buffer":[[5,6,1,"","parm"],[5,6,1,"","value"]],"tomato.drivers.biologic.kbio.kbio_api":[[5,5,1,"","KBIO_api"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api":[[5,8,1,"","BL_Error"],[5,5,1,"","ChannelInfo"],[5,7,1,"","Connect"],[5,7,1,"","ConvertNumericIntoSingle"],[5,7,1,"","DefineBoolParameter"],[5,7,1,"","DefineIntParameter"],[5,7,1,"","DefineParameter"],[5,7,1,"","DefineSglParameter"],[5,5,1,"","DeviceInfo"],[5,7,1,"","Disconnect"],[5,5,1,"","Error"],[5,7,1,"","FindEChemDev"],[5,7,1,"","FindEChemEthDev"],[5,7,1,"","FindEChemUsbDev"],[5,8,1,"","FindError"],[5,7,1,"","GetChannelInfo"],[5,7,1,"","GetCurrentValues"],[5,7,1,"","GetData"],[5,7,1,"","GetErrorMsg"],[5,7,1,"","GetHardwareConf"],[5,7,1,"","GetLibVersion"],[5,7,1,"","GetMessage"],[5,7,1,"","GetParamInfos"],[5,7,1,"","GetTechniqueInfos"],[5,5,1,"","HardwareConf"],[5,7,1,"","LoadFirmware"],[5,7,1,"","LoadTechnique"],[5,7,1,"","OptionError"],[5,7,1,"","PluggedChannels"],[5,7,1,"","SetEthernetConfig"],[5,7,1,"","SetHardwareConf"],[5,7,1,"","StartChannel"],[5,7,1,"","StartChannels"],[5,7,1,"","StopChannel"],[5,7,1,"","StopChannels"],[5,7,1,"","TestComSpeed"],[5,7,1,"","TestConnection"],[5,7,1,"","USB_DeviceInfo"],[5,7,1,"","UpdateParameters"],[5,7,1,"","bind_function"],[5,9,1,"","blfind_api"],[5,7,1,"","channel_map"],[5,9,1,"","ecl_api"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.BL_Error":[[5,7,1,"","is_error"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.ChannelInfo":[[5,6,1,"","amplifier"],[5,6,1,"","board"],[5,6,1,"","firmware"],[5,6,1,"","has_no_firmware"],[5,6,1,"","is_kernel_loaded"],[5,6,1,"","max_IRange"],[5,6,1,"","min_IRange"],[5,6,1,"","state"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.DeviceInfo":[[5,6,1,"","model"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.Error":[[5,7,1,"","check"],[5,7,1,"","is_error"],[5,9,1,"","list_by_tag"],[5,6,1,"","translate"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.FindError":[[5,9,1,"","list_by_tag"]],"tomato.drivers.biologic.kbio.kbio_api.KBIO_api.HardwareConf":[[5,6,1,"","connection"],[5,6,1,"","mode"]],"tomato.drivers.biologic.kbio.kbio_tech":[[5,5,1,"","ECC_parm"],[5,4,1,"","make_ecc_parm"],[5,4,1,"","make_ecc_parms"],[5,4,1,"","print_experiment_data"]],"tomato.drivers.biologic.kbio.kbio_tech.ECC_parm":[[5,9,1,"","label"],[5,9,1,"","type_"]],"tomato.drivers.biologic.kbio.kbio_types":[[5,5,1,"","AMPLIFIER"],[5,5,1,"","BANDWIDTH"],[5,5,1,"","CHANNEL_BOARD"],[5,9,1,"","CH_INFO"],[5,9,1,"","CURRENT_VALUES"],[5,5,1,"","ChannelInfo"],[5,9,1,"","ChannelsArray"],[5,5,1,"","CurrentValues"],[5,9,1,"","DATA_INFO"],[5,5,1,"","DEVICE"],[5,9,1,"","DEVICE_INFO"],[5,9,1,"","DataBuffer"],[5,5,1,"","DataInfo"],[5,5,1,"","DeviceInfo"],[5,9,1,"","ECC_PARM"],[5,9,1,"","ECC_PARMS"],[5,4,1,"","ECC_PARM_ARRAY"],[5,5,1,"","ERROR"],[5,5,1,"","E_RANGE"],[5,5,1,"","EccParam"],[5,5,1,"","EccParams"],[5,5,1,"","Ethernet_device"],[5,5,1,"","FILTER"],[5,5,1,"","FIND_ERROR"],[5,5,1,"","FIRMWARE"],[5,5,1,"","GAIN"],[5,5,1,"","HW_CNX"],[5,9,1,"","HW_CONF"],[5,5,1,"","HW_MODE"],[5,5,1,"","HardwareConf"],[5,5,1,"","I_RANGE"],[5,5,1,"","OPTION_ERROR"],[5,5,1,"","PARAM_TYPE"],[5,5,1,"","PROG_STATE"],[5,9,1,"","ResultsArray"],[5,9,1,"","TECHNIQUE_INFOS"],[5,5,1,"","TechniqueInfos"],[5,5,1,"","USB_device"]],"tomato.drivers.biologic.kbio.kbio_types.AMPLIFIER":[[5,9,1,"","AMPL3_200A12V"],[5,9,1,"","AMPL3_50A60V"],[5,9,1,"","AMPL3_50A60VII"],[5,9,1,"","AMPL4_10A5V"],[5,9,1,"","AMPL4_1A48VPII"],[5,9,1,"","AMPL4_1A48VPIII"],[5,9,1,"","AMPL4_2A30V"],[5,9,1,"","AMPL4_30A50V"],[5,9,1,"","AMPL_100A5V"],[5,9,1,"","AMPL_10A"],[5,9,1,"","AMPL_10A_MPG2B"],[5,9,1,"","AMPL_1A"],[5,9,1,"","AMPL_1A48V"],[5,9,1,"","AMPL_20A"],[5,9,1,"","AMPL_20A_MPG2B"],[5,9,1,"","AMPL_2A"],[5,9,1,"","AMPL_40A_MPG2B"],[5,9,1,"","AMPL_4A14V"],[5,9,1,"","AMPL_4AI"],[5,9,1,"","AMPL_4AI_VSP"],[5,9,1,"","AMPL_5A"],[5,9,1,"","AMPL_5A_MPG2B"],[5,9,1,"","AMPL_80A"],[5,9,1,"","AMPL_8AI"],[5,9,1,"","AMPL_COIN_CELL_HOLDER"],[5,9,1,"","AMPL_ERROR"],[5,9,1,"","AMPL_HEUS"],[5,9,1,"","AMPL_LB2000"],[5,9,1,"","AMPL_LB500"],[5,9,1,"","AMPL_LC"],[5,9,1,"","AMPL_LC_VSP"],[5,9,1,"","AMPL_MUIC"],[5,9,1,"","AMPL_NONE"],[5,9,1,"","AMPL_PAC"],[5,9,1,"","AMPL_UNDEF"]],"tomato.drivers.biologic.kbio.kbio_types.BANDWIDTH":[[5,9,1,"","BW_1"],[5,9,1,"","BW_2"],[5,9,1,"","BW_3"],[5,9,1,"","BW_4"],[5,9,1,"","BW_5"],[5,9,1,"","BW_6"],[5,9,1,"","BW_7"],[5,9,1,"","BW_8"],[5,9,1,"","BW_9"]],"tomato.drivers.biologic.kbio.kbio_types.CHANNEL_BOARD":[[5,9,1,"","C340_IF0"],[5,9,1,"","C340_IF2_NONZ"],[5,9,1,"","C340_IF2_Z"],[5,9,1,"","C340_IF3_NONZ"],[5,9,1,"","C340_IF3_NZZ"],[5,9,1,"","C340_IF3_Z"],[5,9,1,"","C340_IF3_ZZ"],[5,9,1,"","C340_OTHERS"],[5,9,1,"","C340_SP150NZ"],[5,9,1,"","C340_SP150Z"],[5,9,1,"","C340_SP50"],[5,9,1,"","C437_MPG2"],[5,9,1,"","C437_MPG2Z"],[5,9,1,"","C437_MPGX"],[5,9,1,"","C437_MPGXZ"],[5,9,1,"","C437_NZ"],[5,9,1,"","C437_SP150NZ"],[5,9,1,"","C437_SP150Z"],[5,9,1,"","C437_VMP3ENZ"],[5,9,1,"","C437_VMP3EZ"],[5,9,1,"","C437_Z"]],"tomato.drivers.biologic.kbio.kbio_types.ChannelInfo":[[5,9,1,"","AmpCode"],[5,9,1,"","BoardSerialNumber"],[5,9,1,"","BoardVersion"],[5,9,1,"","Channel"],[5,9,1,"","FirmwareCode"],[5,9,1,"","FirmwareVersion"],[5,9,1,"","GPRAboard"],[5,9,1,"","Lcboard"],[5,9,1,"","MUXboard"],[5,9,1,"","MaxBandwidth"],[5,9,1,"","MaxIRange"],[5,9,1,"","MemFilled"],[5,9,1,"","MemSize"],[5,9,1,"","MinIRange"],[5,9,1,"","NbAmps"],[5,9,1,"","NbOfTechniques"],[5,9,1,"","State"],[5,9,1,"","XilinxVersion"],[5,9,1,"","Zboard"]],"tomato.drivers.biologic.kbio.kbio_types.CurrentValues":[[5,9,1,"","Ece"],[5,9,1,"","EceRangeMax"],[5,9,1,"","EceRangeMin"],[5,9,1,"","ElapsedTime"],[5,9,1,"","Eoverflow"],[5,9,1,"","Ewe"],[5,9,1,"","EweRangeMax"],[5,9,1,"","EweRangeMin"],[5,9,1,"","Freq"],[5,9,1,"","I"],[5,9,1,"","IRange"],[5,9,1,"","Ioverflow"],[5,9,1,"","MemFilled"],[5,9,1,"","OptErr"],[5,9,1,"","OptPos"],[5,9,1,"","Rcomp"],[5,9,1,"","Saturation"],[5,9,1,"","State"],[5,9,1,"","TimeBase"]],"tomato.drivers.biologic.kbio.kbio_types.DEVICE":[[5,9,1,"","BCS815"],[5,9,1,"","BISTAT"],[5,9,1,"","BISTAT2"],[5,9,1,"","BP300"],[5,9,1,"","CLB2000"],[5,9,1,"","CLB500"],[5,9,1,"","EPP400"],[5,9,1,"","EPP4000"],[5,9,1,"","FCT150S"],[5,9,1,"","FCT50S"],[5,9,1,"","HCP1005"],[5,9,1,"","HCP803"],[5,9,1,"","KINEXXX"],[5,9,1,"","MCS_200"],[5,9,1,"","MOSLED"],[5,9,1,"","MPG"],[5,9,1,"","MPG2"],[5,9,1,"","MPG205"],[5,9,1,"","MPG210"],[5,9,1,"","MPG220"],[5,9,1,"","MPG240"],[5,9,1,"","SP100"],[5,9,1,"","SP150"],[5,9,1,"","SP150E"],[5,9,1,"","SP200"],[5,9,1,"","SP240"],[5,9,1,"","SP300"],[5,9,1,"","SP50"],[5,9,1,"","SP50E"],[5,9,1,"","UNKNOWN"],[5,9,1,"","VMP"],[5,9,1,"","VMP2"],[5,9,1,"","VMP3"],[5,9,1,"","VMP300"],[5,9,1,"","VMP3E"],[5,9,1,"","VSP"],[5,9,1,"","VSP300"],[5,9,1,"","VSP3E"]],"tomato.drivers.biologic.kbio.kbio_types.DataInfo":[[5,9,1,"","IRQskipped"],[5,9,1,"","MuxPad"],[5,9,1,"","NbCols"],[5,9,1,"","NbRows"],[5,9,1,"","ProcessIndex"],[5,9,1,"","StartTime"],[5,9,1,"","TechniqueID"],[5,9,1,"","TechniqueIndex"],[5,9,1,"","loop"]],"tomato.drivers.biologic.kbio.kbio_types.DeviceInfo":[[5,9,1,"","CPU"],[5,9,1,"","DeviceCode"],[5,9,1,"","FirmwareDate_dd"],[5,9,1,"","FirmwareDate_mm"],[5,9,1,"","FirmwareDate_yyyy"],[5,9,1,"","FirmwareVersion"],[5,9,1,"","HTdisplayOn"],[5,9,1,"","NbOfConnectedPC"],[5,9,1,"","NumberOfChannels"],[5,9,1,"","NumberOfSlots"],[5,9,1,"","RAMSize"]],"tomato.drivers.biologic.kbio.kbio_types.ERROR":[[5,9,1,"","COMM_ALLOCMEMFAILED"],[5,9,1,"","COMM_COMMFAILED"],[5,9,1,"","COMM_CONNECTIONFAILED"],[5,9,1,"","COMM_INCOMPATIBLESERVER"],[5,9,1,"","COMM_INVALIDIPADDRESS"],[5,9,1,"","COMM_LOADFIRMWAREFAILED"],[5,9,1,"","COMM_MAXCONNREACHED"],[5,9,1,"","COMM_WAITINGACK"],[5,9,1,"","FIRM_FIRMFILEACCESSFAILED"],[5,9,1,"","FIRM_FIRMFILENOTEXISTS"],[5,9,1,"","FIRM_FIRMINVALIDFILE"],[5,9,1,"","FIRM_FIRMLOADINGFAILED"],[5,9,1,"","FIRM_FIRMWAREINCOMPATIBLE"],[5,9,1,"","FIRM_FIRMWARENOTLOADED"],[5,9,1,"","FIRM_XILFILEACCESSFAILED"],[5,9,1,"","FIRM_XILFILENOTEXISTS"],[5,9,1,"","FIRM_XILINVALIDFILE"],[5,9,1,"","FIRM_XILLOADINGFAILED"],[5,9,1,"","GEN_CHANNELNOTPLUGGED"],[5,9,1,"","GEN_CHANNEL_RUNNING"],[5,9,1,"","GEN_CONNECTIONINPROGRESS"],[5,9,1,"","GEN_DEVICE_NOTALLOWED"],[5,9,1,"","GEN_ECLAB_LOADED"],[5,9,1,"","GEN_FILENOTEXISTS"],[5,9,1,"","GEN_FUNCTIONFAILED"],[5,9,1,"","GEN_FUNCTIONINPROGRESS"],[5,9,1,"","GEN_INVALIDCONF"],[5,9,1,"","GEN_INVALIDPARAMETERS"],[5,9,1,"","GEN_LIBNOTCORRECTLYLOADED"],[5,9,1,"","GEN_NOCHANNELSELECTED"],[5,9,1,"","GEN_NOTCONNECTED"],[5,9,1,"","GEN_UPDATEPARAMETERS"],[5,9,1,"","GEN_USBLIBRARYERROR"],[5,9,1,"","INSTR_MSGSIZEERROR"],[5,9,1,"","INSTR_RESPERROR"],[5,9,1,"","INSTR_RESPNOTPOSSIBLE"],[5,9,1,"","INSTR_TOOMANYDATA"],[5,9,1,"","INSTR_VMEERROR"],[5,9,1,"","NOERROR"],[5,9,1,"","OPT_10A5V_BADPOWER"],[5,9,1,"","OPT_10A5V_ERROR"],[5,9,1,"","OPT_10A5V_OVERTEMP"],[5,9,1,"","OPT_10A5V_POWERFAIL"],[5,9,1,"","OPT_1A48VP_BADPOWER"],[5,9,1,"","OPT_1A48VP_ERROR"],[5,9,1,"","OPT_1A48VP_OVERTEMP"],[5,9,1,"","OPT_1A48VP_POWERFAIL"],[5,9,1,"","OPT_48V_BADPOWER"],[5,9,1,"","OPT_48V_ERROR"],[5,9,1,"","OPT_48V_OVERTEMP"],[5,9,1,"","OPT_48V_POWERFAIL"],[5,9,1,"","OPT_4A_BADPOWER"],[5,9,1,"","OPT_4A_ERROR"],[5,9,1,"","OPT_4A_OVERTEMP"],[5,9,1,"","OPT_4A_POWERFAIL"],[5,9,1,"","OPT_CHANGE"],[5,9,1,"","OPT_OPEN_IN"],[5,9,1,"","TECH_DATACORRUPTED"],[5,9,1,"","TECH_ECCFILECORRUPTED"],[5,9,1,"","TECH_ECCFILENOTEXISTS"],[5,9,1,"","TECH_INCOMPATIBLEECC"],[5,9,1,"","TECH_LOADTECHNIQUEFAILED"],[5,9,1,"","TECH_MEMFULL"]],"tomato.drivers.biologic.kbio.kbio_types.E_RANGE":[[5,9,1,"","E_RANGE_10V"],[5,9,1,"","E_RANGE_2_5V"],[5,9,1,"","E_RANGE_5V"],[5,9,1,"","E_RANGE_AUTO"]],"tomato.drivers.biologic.kbio.kbio_types.EccParam":[[5,9,1,"","ParamIndex"],[5,9,1,"","ParamStr"],[5,9,1,"","ParamType"],[5,9,1,"","ParamVal"]],"tomato.drivers.biologic.kbio.kbio_types.EccParams":[[5,9,1,"","len"],[5,9,1,"","pParams"]],"tomato.drivers.biologic.kbio.kbio_types.Ethernet_device":[[5,9,1,"","config"],[5,9,1,"","identifier"],[5,9,1,"","instrument"],[5,9,1,"","name"],[5,9,1,"","serial"]],"tomato.drivers.biologic.kbio.kbio_types.FILTER":[[5,9,1,"","FILTER_1KHZ"],[5,9,1,"","FILTER_50KHZ"],[5,9,1,"","FILTER_5HZ"],[5,9,1,"","FILTER_NONE"]],"tomato.drivers.biologic.kbio.kbio_types.FIND_ERROR":[[5,9,1,"","ACK_TIMEOUT"],[5,9,1,"","CFG_MODIFY_FAILED"],[5,9,1,"","CMD_FAILED"],[5,9,1,"","EMPTY_PARAM"],[5,9,1,"","EXP_RUNNING"],[5,9,1,"","FIND_FAILED"],[5,9,1,"","GW_FORMAT"],[5,9,1,"","INVALID_PARAMETER"],[5,9,1,"","IP_ALREADYEXIST"],[5,9,1,"","IP_FORMAT"],[5,9,1,"","IP_NOT_FOUND"],[5,9,1,"","NM_FORMAT"],[5,9,1,"","NO_ERROR"],[5,9,1,"","READ_PARAM_FAILED"],[5,9,1,"","SOCKET_READ"],[5,9,1,"","SOCKET_WRITE"],[5,9,1,"","UNKNOWN_ERROR"]],"tomato.drivers.biologic.kbio.kbio_types.FIRMWARE":[[5,9,1,"","ECAL"],[5,9,1,"","ECAL4"],[5,9,1,"","INTERPR"],[5,9,1,"","INVALID"],[5,9,1,"","KERNEL"],[5,9,1,"","NONE"],[5,9,1,"","UNKNOWN"]],"tomato.drivers.biologic.kbio.kbio_types.GAIN":[[5,9,1,"","GAIN_1"],[5,9,1,"","GAIN_10"],[5,9,1,"","GAIN_100"],[5,9,1,"","GAIN_1000"]],"tomato.drivers.biologic.kbio.kbio_types.HW_CNX":[[5,9,1,"","CE_TO_GND"],[5,9,1,"","HIGH_VOLTAGE"],[5,9,1,"","STANDARD"],[5,9,1,"","WE_TO_GND"]],"tomato.drivers.biologic.kbio.kbio_types.HW_MODE":[[5,9,1,"","FLOATING"],[5,9,1,"","GROUNDED"]],"tomato.drivers.biologic.kbio.kbio_types.HardwareConf":[[5,9,1,"","Connection"],[5,9,1,"","Mode"]],"tomato.drivers.biologic.kbio.kbio_types.I_RANGE":[[5,9,1,"","I_RANGE_100mA"],[5,9,1,"","I_RANGE_100nA"],[5,9,1,"","I_RANGE_100pA"],[5,9,1,"","I_RANGE_100uA"],[5,9,1,"","I_RANGE_10mA"],[5,9,1,"","I_RANGE_10nA"],[5,9,1,"","I_RANGE_10uA"],[5,9,1,"","I_RANGE_1A"],[5,9,1,"","I_RANGE_1mA"],[5,9,1,"","I_RANGE_1nA"],[5,9,1,"","I_RANGE_1uA"],[5,9,1,"","I_RANGE_AUTO"],[5,9,1,"","I_RANGE_BOOSTER"],[5,9,1,"","I_RANGE_KEEP"]],"tomato.drivers.biologic.kbio.kbio_types.OPTION_ERROR":[[5,9,1,"","IRCMP_OVR"],[5,9,1,"","NO_ERROR"],[5,9,1,"","OPEN_IN"],[5,9,1,"","OPT_10A5V_BADPOW"],[5,9,1,"","OPT_10A5V_ERR"],[5,9,1,"","OPT_10A5V_OVRTEMP"],[5,9,1,"","OPT_10A5V_POWFAIL"],[5,9,1,"","OPT_48V"],[5,9,1,"","OPT_48V_BADPOW"],[5,9,1,"","OPT_48V_OVRTEMP"],[5,9,1,"","OPT_48V_POWFAIL"],[5,9,1,"","OPT_4A"],[5,9,1,"","OPT_4A_BADPOW"],[5,9,1,"","OPT_4A_OVRTEMP"],[5,9,1,"","OPT_4A_POWFAIL"],[5,9,1,"","OPT_CHANGE"]],"tomato.drivers.biologic.kbio.kbio_types.PARAM_TYPE":[[5,9,1,"","PARAM_BOOLEAN"],[5,9,1,"","PARAM_INT"],[5,9,1,"","PARAM_SINGLE"]],"tomato.drivers.biologic.kbio.kbio_types.PROG_STATE":[[5,9,1,"","PAUSE"],[5,9,1,"","RUN"],[5,9,1,"","STOP"],[5,9,1,"","SYNC"]],"tomato.drivers.biologic.kbio.kbio_types.TechniqueInfos":[[5,9,1,"","HardSettings"],[5,9,1,"","Id"],[5,9,1,"","Params"],[5,9,1,"","indx"],[5,9,1,"","nbParams"],[5,9,1,"","nbSettings"]],"tomato.drivers.biologic.kbio.kbio_types.USB_device":[[5,6,1,"","address"],[5,9,1,"","index"],[5,9,1,"","instrument"],[5,9,1,"","serial"]],"tomato.drivers.biologic.kbio.tech_types":[[5,5,1,"","TECH_ID"]],"tomato.drivers.biologic.kbio.tech_types.TECH_ID":[[5,9,1,"","CA"],[5,9,1,"","CALIMIT"],[5,9,1,"","CASG"],[5,9,1,"","CASP"],[5,9,1,"","CGA"],[5,9,1,"","CLOAD"],[5,9,1,"","COKINE"],[5,9,1,"","CP"],[5,9,1,"","CPLIMIT"],[5,9,1,"","CPO"],[5,9,1,"","CPOWER"],[5,9,1,"","CPP"],[5,9,1,"","CV"],[5,9,1,"","CVA"],[5,9,1,"","DNPV"],[5,9,1,"","DPA"],[5,9,1,"","DPV"],[5,9,1,"","EVT"],[5,9,1,"","FCT"],[5,9,1,"","GALPULSE"],[5,9,1,"","GC"],[5,9,1,"","GDYN"],[5,9,1,"","GDYNLIMIT"],[5,9,1,"","GEIS"],[5,9,1,"","GZIR"],[5,9,1,"","LASV"],[5,9,1,"","LOOP"],[5,9,1,"","LP"],[5,9,1,"","MIR"],[5,9,1,"","MP"],[5,9,1,"","NONE"],[5,9,1,"","NPV"],[5,9,1,"","OCV"],[5,9,1,"","PDP"],[5,9,1,"","PDYN"],[5,9,1,"","PDYNLIMIT"],[5,9,1,"","PEIS"],[5,9,1,"","POTPULSE"],[5,9,1,"","PSP"],[5,9,1,"","PZIR"],[5,9,1,"","RNPV"],[5,9,1,"","SGEIS"],[5,9,1,"","SPEIS"],[5,9,1,"","STACKGDYN"],[5,9,1,"","STACKGDYN_SLAVE"],[5,9,1,"","STACKGEIS"],[5,9,1,"","STACKGEIS_SLAVE"],[5,9,1,"","STACKPDYN"],[5,9,1,"","STACKPDYN_SLAVE"],[5,9,1,"","STACKPEIS"],[5,9,1,"","STACKPEIS_SLAVE"],[5,9,1,"","SWV"],[5,9,1,"","TI"],[5,9,1,"","TO"],[5,9,1,"","TOS"],[5,9,1,"","ZRA"]],"tomato.drivers.biologic.kbio.utils":[[5,4,1,"","class_name"],[5,4,1,"","error_diff"],[5,4,1,"","exception_brief"],[5,4,1,"","file_complete"],[5,4,1,"","pp_plural"],[5,4,1,"","prepend_path"],[5,4,1,"","warn_diff"]],"tomato.drivers.biologic.kbio_wrapper":[[4,4,1,"","current"],[4,4,1,"","dsl_to_ecc"],[4,4,1,"","get_kbio_api"],[4,4,1,"","get_kbio_techpath"],[4,4,1,"","get_num_steps"],[4,4,1,"","get_test_magic"],[4,4,1,"","pad_steps"],[4,4,1,"","parse_raw_data"],[4,4,1,"","payload_to_ecc"],[4,4,1,"","translate"],[4,4,1,"","vlimit"]],"tomato.drivers.biologic.main":[[4,4,1,"","get_data"],[4,4,1,"","get_status"],[4,4,1,"","start_job"],[4,4,1,"","stop_job"]],"tomato.drivers.driver_funcs":[[3,4,1,"","data_poller"],[3,4,1,"","data_snapshot"],[3,4,1,"","driver_api"],[3,4,1,"","driver_reset"],[3,4,1,"","driver_worker"],[3,4,1,"","tomato_job"]],"tomato.drivers.dummy":[[6,3,0,"-","main"]],"tomato.drivers.dummy.main":[[6,4,1,"","get_data"],[6,4,1,"","get_status"],[6,4,1,"","start_job"],[6,4,1,"","stop_job"]],"tomato.drivers.logger_funcs":[[3,4,1,"","log_listener"],[3,4,1,"","log_listener_config"],[3,4,1,"","log_worker_config"]],"tomato.drivers.yadg_funcs":[[3,4,1,"","get_yadg_preset"],[3,4,1,"","process_yadg_preset"]],"tomato.ketchup":[[7,3,0,"-","functions"]],"tomato.ketchup.functions":[[7,4,1,"","cancel"],[7,4,1,"","eject"],[7,4,1,"","load"],[7,4,1,"","ready"],[7,4,1,"","search"],[7,4,1,"","snapshot"],[7,4,1,"","status"],[7,4,1,"","submit"]],"tomato.main":[[0,4,1,"","run_ketchup"],[0,4,1,"","run_tomato"],[0,4,1,"","sync_pipelines_to_state"]],"tomato.setlib":[[8,3,0,"-","functions"]],"tomato.setlib.functions":[[8,5,1,"","LocalDir"],[8,4,1,"","get_dirs"],[8,4,1,"","get_pipelines"],[8,4,1,"","get_settings"]],"tomato.setlib.functions.LocalDir":[[8,9,1,"","user_config_dir"],[8,9,1,"","user_data_dir"],[8,9,1,"","user_log_dir"]],tomato:[[1,3,0,"-","daemon"],[2,3,0,"-","dbhandler"],[3,3,0,"-","drivers"],[7,3,0,"-","ketchup"],[0,3,0,"-","main"],[8,3,0,"-","setlib"]]},objnames:{"0":["py","pydantic_model","Python model"],"1":["py","pydantic_validator","Python validator"],"2":["py","pydantic_field","Python field"],"3":["py","module","Python module"],"4":["py","function","Python function"],"5":["py","class","Python class"],"6":["py","property","Python property"],"7":["py","method","Python method"],"8":["py","exception","Python exception"],"9":["py","attribute","Python attribute"]},objtypes:{"0":"py:pydantic_model","1":"py:pydantic_validator","2":"py:pydantic_field","3":"py:module","4":"py:function","5":"py:class","6":"py:property","7":"py:method","8":"py:exception","9":"py:attribute"},terms:{"0":[4,5,11],"00":[7,12],"02":7,"05":7,"06":[7,12],"08":7,"1":[4,5,6,7,11],"10":[4,5,7,11],"100":[4,5],"101":5,"102":5,"103":5,"1035":7,"104":5,"105":5,"106":5,"107":5,"108":5,"109":[5,11],"10a":5,"11":[5,11,12],"110":5,"111":5,"112":5,"113":5,"114":5,"115":5,"116":5,"117":5,"118":5,"119":5,"12":[5,11],"120":5,"121":5,"122":5,"123":5,"124":5,"125":5,"126":5,"127":5,"128":5,"129":5,"13":[5,11],"130":5,"131":5,"132":5,"133":5,"134":5,"135":5,"136":5,"137":5,"138":5,"139":5,"14":[5,11],"140":5,"141":5,"142":5,"15":[5,11],"150":5,"151":5,"152":5,"153":5,"155":5,"156":5,"157":5,"158":5,"159":5,"16":[5,11],"167":5,"169":5,"17":5,"170":5,"17584":7,"18":[5,12],"19":5,"192":11,"1a48vp":5,"1rc11":11,"2":[4,5,7,9,11],"20":[3,5],"200":5,"201":5,"202":5,"2022":[7,12],"203":5,"204":5,"205":5,"206":5,"207":5,"209":11,"21":[5,12],"22":[5,12],"229213":7,"23":5,"24":5,"25":5,"255":5,"26":5,"27":5,"28":5,"29":5,"2a1":11,"3":[5,7,11],"30":[5,12],"300":5,"301":5,"302":5,"303":5,"304":5,"305":5,"306":5,"307":5,"308":5,"309":5,"31":5,"32":5,"32b":5,"33":5,"34":5,"35":5,"36":5,"3600":11,"38":5,"39":5,"4":[5,7,11],"400":5,"401":5,"402":5,"403":5,"404":5,"405":5,"48v":5,"49":7,"4a":5,"5":[4,5,7,11],"538448":12,"578619":7,"5v":5,"6":[5,11],"60":11,"600":5,"601":5,"602":5,"603":5,"7":[5,11],"77":5,"8":[5,11],"9":[5,11],"93":5,"966775":7,"97":5,"983600":12,"boolean":[5,11],"byte":5,"case":5,"class":[5,8,11],"d\u00fcbendorf":13,"default":[5,11,12],"do":[5,7,11,12],"enum":[5,11],"final":11,"float":[4,5,6],"function":[4,5,6,7,8,11,13],"goto":4,"import":5,"int":[4,5,6],"new":[5,7,11],"null":[7,12],"public":13,"return":[0,1,2,3,4,5,6,7,8,12],"static":5,"switch":[7,12],"true":[4,5],"try":12,"while":12,A:[0,3,4,9,11,12],As:[5,11],By:12,For:[11,12],If:[7,11],In:[11,12],Is:4,It:[11,12],No:[4,5,6],Not:6,TO:5,TOS:5,The:[4,5,7,10,11,12],To:[10,11,12],With:7,_ctype:5,_pack_:5,abort:[4,5],about:[11,12],abov:[10,11,12],absolut:4,access:11,accord:5,achiev:5,ack_timeout:5,activ:4,actual:[5,7],add:5,addit:11,additionalproperti:11,address:[3,4,5,6,11,12],after:9,against:[11,12],aim:5,alia:5,align:5,all:[4,7,10,11,12],alloc:5,allow:[4,5,12],alreadi:[5,12],also:[7,11],altern:[7,11],ampcod:5,ampl3_200a12v:5,ampl3_50a60v:5,ampl3_50a60vii:5,ampl4_10a5v:5,ampl4_1a48vpii:5,ampl4_1a48vpiii:5,ampl4_2a30v:5,ampl4_30a50v:5,ampl_100a5v:5,ampl_10a:5,ampl_10a_mpg2b:5,ampl_1a48v:5,ampl_1a:5,ampl_20a:5,ampl_20a_mpg2b:5,ampl_2a:5,ampl_40a_mpg2b:5,ampl_4a14v:5,ampl_4ai:5,ampl_4ai_vsp:5,ampl_5a:5,ampl_5a_mpg2b:5,ampl_80a:5,ampl_8ai:5,ampl_coin_cell_hold:5,ampl_error:5,ampl_heu:5,ampl_lb2000:5,ampl_lb500:5,ampl_lc:5,ampl_lc_vsp:5,ampl_muic:5,ampl_non:5,ampl_pac:5,ampl_undef:5,amplifi:5,an:[4,5,7,9,11,12],an_ext:5,ani:[3,4,5,6,7,12],annot:12,api:[4,5],app:12,appdata:11,appdir:8,append:5,applic:4,ar:[4,5,10,12],arbitrari:4,archiv:[7,11,12],arg:7,argpars:7,argtyp:5,argument:[7,11],around:4,arrai:[5,11],ask:11,assert:5,assign:[7,11],associ:[4,6],assum:11,attempt:[7,12],attribut:[5,11],aurora:13,author:[4,6,7,9,13],autom:[9,12],avail:[4,10,11,12],backend:9,bad:5,bandwidth:5,base:[5,8],basic:13,batch:12,batteri:4,bcs815:5,been:[7,11,12],befor:7,begin:12,behaviour:[5,12],below:[4,6,11],between:[4,5,6],big:13,bin:5,bind_funct:5,bio:5,biolog:[0,3,6,9,11],bistat2:5,bistat:5,bl_connect:5,bl_convertnumericintosingl:5,bl_defineboolparamet:5,bl_defineintparamet:5,bl_definesglparamet:5,bl_disconnect:5,bl_error:5,bl_findechemdev:5,bl_findechemethdev:5,bl_findechemusbdev:5,bl_getchannelinfo:5,bl_getchannelsplug:5,bl_getcurrentvalu:5,bl_getdata:5,bl_geterrormsg:5,bl_gethardconf:5,bl_getlibvers:5,bl_getmessag:5,bl_getopterr:5,bl_getparaminfo:5,bl_gettechniqueinfo:5,bl_getusbdeviceinfo:5,bl_loadfirmwar:5,bl_loadtechniqu:5,bl_setconfig:5,bl_sethardconf:5,bl_startchannel:5,bl_stopchannel:5,bl_testcommspe:5,bl_testconnect:5,bl_updateparamet:5,bl_xxx:5,blfind:5,blfind_api:5,blfind_fil:5,board:5,boardserialnumb:5,boardvers:5,bool:[4,6],both:5,bp300:5,buffer:5,build:[5,10],built:10,bw_1:5,bw_2:5,bw_3:5,bw_4:5,bw_5:5,bw_6:5,bw_7:5,bw_8:5,bw_9:5,c340_if0:5,c340_if2_nonz:5,c340_if2_z:5,c340_if3_nonz:5,c340_if3_nzz:5,c340_if3_z:5,c340_if3_zz:5,c340_other:5,c340_sp150nz:5,c340_sp150z:5,c340_sp50:5,c437_mpg2:5,c437_mpg2z:5,c437_mpgx:5,c437_mpgxz:5,c437_nz:5,c437_sp150nz:5,c437_sp150z:5,c437_vmp3enz:5,c437_vmp3ez:5,c437_z:5,c:[4,5,7,11,12],c_bool:5,c_bool_array_16:5,c_buffer:5,c_byte:5,c_char_p:5,c_dump:5,c_float:5,c_long:5,c_long_array_16:5,c_ubyt:5,c_ulong:5,c_ulong_array_1000:5,c_util:5,ca:5,cach:[4,6],calimit:5,call:[5,7,11],can:[4,5,7,10,11,12],cancel:[7,12],cannot:5,capabl:[11,12],capac:4,captur:5,carri:[11,12],casg:5,casp:5,cc:4,cd:[7,10,12],ce:12,ce_to_gnd:5,cell:4,cfg_modify_fail:5,cga:5,ch:5,ch_info:5,chang:[5,12],channel:[3,4,5,6,11],channel_board:5,channel_map:5,channel_set:5,channelinfo:5,channelsarrai:5,check:[5,7,12],chronoamperometri:4,chronopotentiometri:4,chunk:11,class_nam:5,clb2000:5,clb500:5,clear:5,client:5,cload:5,clone:10,close:5,cmd_fail:5,cmp:5,cnx:5,cobj:5,code:[4,5,6,7,9,13],cokin:5,com:10,combin:11,come:5,comm_allocmemfail:5,comm_commfail:5,comm_connectionfail:5,comm_incompatibleserv:5,comm_invalidipaddress:5,comm_loadfirmwarefail:5,comm_maxconnreach:5,comm_waitingack:5,command:[0,3,5,10,12],commun:5,compat:5,complet:[7,11,12],compon:12,compos:12,cond:4,conda:10,config:[5,11],configpath:8,configur:[0,3,5,9,11,12],connect:[5,11],consist:[5,12],constant:5,constant_curr:[4,11],constant_voltag:[4,11],contain:[4,5,6,7,10,11,12],content:5,context:5,continu:4,contribut:13,control:[3,5],convent:5,convers:[9,13],convert:[4,5],convertnumericintosingl:5,copi:12,correctli:5,correspond:[4,6,11,13],corrupt:5,coupl:5,cp:5,cplimit:5,cpo:5,cpower:5,cpp:5,cpu:5,creat:[5,7,10,12],criteria:12,critic:11,ctype:5,current:[3,6,7,9,10,12],current_valu:5,currentvalu:5,custom_nam:7,cv:[4,5],cva:5,cwd:12,d2:13,d:4,daemon:[0,7,9,11],data:[4,5,6,7,11],data_info:5,data_pol:3,data_snapshot:3,databas:11,databuff:5,dataclass:5,datafram:13,datagram:12,datainfo:5,datapath:8,datapoint:[4,6],datatyp:5,date:[7,12],db:11,dbhandler:[0,7],dbpath:[0,2],debug:[6,11],decid:5,decod:5,defin:11,defineboolparamet:5,defineintparamet:5,defineparamet:5,definesglparamet:5,definit:11,delai:[4,6],deliver:13,delta:4,depend:11,describ:[4,6],descript:[5,11],deseri:5,detail:12,develop:[4,5,9,11,13],devic:[3,4,5,6,9,12],device_info:5,devicecod:5,deviceinfo:5,devnam:4,dgbowl:[10,11],dgbowl_schema:11,diagnost:12,dict:[3,4,5,6,8],digit:[11,12],directori:7,disconnect:5,displai:5,dll:[4,5,6],dllpath:[4,6,11],dnpv:5,doc:10,docstr:5,document:[3,5,10,12],doe:5,done:11,dpa:5,dpv:5,driver:[0,10,11],driver_api:3,driver_func:3,driver_reset:3,driver_work:3,dsl:4,dsl_to_ecc:4,dummi:[0,3,7,9,10],dummy_random_2:7,dummy_random_2_0:7,dummy_sequential_1_0:7,dump:5,e:5,e_rang:[4,5],e_range_10v:5,e_range_2_5v:5,e_range_5v:5,e_range_auto:5,each:11,easiest:11,ec:[4,5,11],ecal4:5,ecal:5,ecc:5,ecc_parm:5,ecc_parm_arrai:5,ecc_parm_list:5,eccparam:[4,5],ecerangemax:5,ecerangemin:5,ecl_api:5,eclib:5,eclib_fil:5,either:5,eject:[7,12],elapsedtim:5,element:7,embed:5,empa:[9,13],empti:[7,12],empty_param:5,encapsul:5,encod:5,energi:[9,13],enter:[11,12],entri:[5,11],enumer:5,env:11,environ:10,eoverflow:5,epfl:13,epp4000:5,epp400:5,equival:5,ercol:[9,13],error:[5,11,12],error_diff:5,establish:5,ethernet:5,ethernet_devic:5,even:[7,12],evt:5,ew:5,ewerangemax:5,ewerangemin:5,exampl:[7,11],except:5,exception_brief:5,exclud:12,execut:[0,4,5,6,7,11,12],exist:[5,7,12],exit_on_limit:4,exp_run:5,expect:11,experi:5,experiment:[11,12],explan:5,extend:5,extens:5,extra:11,extract:5,extract_methodfil:11,extract_samplefil:11,fail:[5,12],fair:[7,11],fals:[1,2,4,5,8,11],fault:12,fct150:5,fct50:5,fct:5,few:5,field:[5,11],file:[4,5,6,7,12],file_complet:5,filenam:[5,12],filter:5,filter_1khz:5,filter_50khz:5,filter_5hz:5,filter_non:5,find:[5,7,11,12],find_error:5,find_fail:5,findechemdev:5,findechemethdev:5,findechemusbdev:5,finderror:5,finish:[7,12],firm_firmfileaccessfail:5,firm_firmfilenotexist:5,firm_firminvalidfil:5,firm_firmloadingfail:5,firm_firmwareincompat:5,firm_firmwarenotload:5,firm_xilfileaccessfail:5,firm_xilfilenotexist:5,firm_xilinvalidfil:5,firm_xilloadingfail:5,firmwar:5,firmwarecod:5,firmwaredate_dd:5,firmwaredate_mm:5,firmwaredate_yyyi:5,firmwarevers:5,first:[4,5,10,12,13],flag:5,folder:[4,10,11,12],follow:[4,5,12],forc:5,format:[5,11,12],found:5,fpga:5,freq:5,frequenc:11,friendli:5,from:[4,5,6,7,10,11,12,13],full:[5,12],further:[5,12],gain:5,gain_1000:5,gain_100:5,gain_10:5,gain_1:5,galpuls:5,gatewai:5,gc:5,gdyn:5,gdynlimit:5,gei:5,gen_channel_run:5,gen_channelnotplug:5,gen_connectioninprogress:5,gen_device_notallow:5,gen_eclab_load:5,gen_filenotexist:5,gen_functionfail:5,gen_functioninprogress:5,gen_invalidconf:5,gen_invalidparamet:5,gen_libnotcorrectlyload:5,gen_nochannelselect:5,gen_notconnect:5,gen_updateparamet:5,gen_usblibraryerror:5,gener:[3,5,7,11,12],get:[4,6,7],get_data:[4,6],get_db_conn:2,get_dir:8,get_kbio_api:4,get_kbio_techpath:4,get_num_step:4,get_pipelin:8,get_set:8,get_statu:[4,6],get_test_mag:4,get_yadg_preset:3,getchannelinfo:5,getcurrentvalu:5,getdata:5,geterrormsg:5,gethardwareconf:5,getlibvers:5,getmessag:5,getparaminfo:5,gettechniqueinfo:5,git:10,github:10,give:5,given:[5,7],goe:3,gpraboard:5,ground:5,guid:[9,12],gw_format:5,gzir:5,ha:[5,7,11,12],handl:5,happen:5,hardset:5,hardwar:11,hardwareconf:5,has_no_firmwar:5,have:12,hcp1005:5,hcp803:5,helper:5,here:[3,11],hex:5,high_voltag:5,home:11,how:12,htdisplayon:5,http:10,hw_cnx:5,hw_conf:5,hw_mode:5,i:5,i_rang:[4,5],i_range_100ma:5,i_range_100na:5,i_range_100pa:5,i_range_100ua:5,i_range_10ma:5,i_range_10na:5,i_range_10ua:5,i_range_1a:5,i_range_1ma:5,i_range_1na:5,i_range_1ua:5,i_range_auto:5,i_range_boost:5,i_range_keep:5,id:[4,5,6],id_:5,identifi:[5,7,11],implement:12,includ:[7,9,12],increas:[6,7],index:[4,5,6],individu:11,indx:5,info:[5,7,11],inform:[4,11,12],initi:13,insert:7,instal:[9,11],instanc:[6,12],instr_msgsizeerror:5,instr_resperror:5,instr_respnotposs:5,instr_toomanydata:5,instr_vmeerror:5,instruct:12,instrument:[4,5,9,11,12],integ:11,interact:7,interfac:[0,5],intern:[5,11],interpr:5,intricaci:5,invalid:5,invalid_paramet:5,investig:12,invoc:12,ioverflow:5,ip:[4,5,6],ip_alreadyexist:5,ip_format:5,ip_not_found:5,ipc:9,irang:5,ircmp_ovr:5,irqskip:5,is_delta:4,is_error:5,is_kernel_load:5,item:11,iter:5,its:[5,7,11,12],ix:5,j:7,job:[4,6,7,9,11],job_get_al:2,job_get_all_queu:2,job_get_info:2,job_set_statu:2,job_set_tim:2,jobdir:3,jobfold:3,jobid:[2,3,7,12],jobnam:[2,7,12],jobqueu:[3,4,6],jq:3,json:[7,11,12],jump:4,just:5,kbio:[3,4],kbio_api:5,kbio_tech:5,kbio_typ:5,kbio_wrapp:4,keep:5,kei:[5,12],kernel:5,ketchup:[0,9],kill:7,kinexxx:5,known:12,krau:[4,6,7,9,13],krpe:11,kwarg:[3,4,6],lab:[5,9,11,13],label:5,languag:4,last:5,lasv:5,launch:10,lausann:13,lcboard:5,least:11,leav:5,len:5,length:5,level:5,lib:4,librari:[4,5],limit:3,limit_current_max:4,limit_current_min:4,limit_voltage_max:4,limit_voltage_min:4,line:[0,11],linear:4,linux:11,list:[2,4,5,6,7,11,12],list_by_tag:5,liter:[4,6,11],load:[5,7,12],loadfirmwar:5,loadtechniqu:5,local:[5,11],localappdata:11,localdir:8,locat:[11,12],lock:4,lockfil:4,lockpath:4,log:[6,11,12],log_listen:3,log_listener_config:3,log_worker_config:3,logfil:3,logger:[3,4,6],logger_func:3,logic:[4,5],loglevel:[3,11],look:11,loop:[3,5,11],lori:[9,13],low:5,lp:5,lp_c_float:5,lp_c_long:5,lp_c_ulong:5,lp_channelinfo:5,lp_currentvalu:5,lp_datainfo:5,lp_deviceinfo:5,lp_eccparam:5,lp_hardwareconf:5,lp_techniqueinfo:5,lq:3,ls:7,lsc:4,lsv:4,ma:4,mai:11,main:[0,1,4,5,6,7,11],main_loop:[1,7],make_ecc_parm:5,manag:[7,11,12],mani:[5,12],map:13,mark:[7,12],match:[7,11,12],materi:[9,13],max_irang:5,maxbandwidth:5,maximum:[4,5],maxirang:5,mcs_200:5,mean:[4,6,12],measur:4,mechan:12,meet:12,member:5,memfil:5,memori:5,memsiz:5,messag:5,metadata:[4,6],method:[0,3,5,11],methodfil:11,mimic:5,min_irang:5,minimum:4,minirang:5,mir:5,mismatch:5,mode:[4,5,11,12],model:[5,9,11],modifi:5,modul:[0,3,5,7,9,11,12,13],more:[5,12],mosl:5,most:5,mp:5,mpg205:5,mpg210:5,mpg220:5,mpg240:5,mpg2:[5,11],mpg:5,msg:5,multi:11,multiindex:13,multipl:[11,12],multiprocess:6,must:12,muxboard:5,muxpad:5,n:11,n_goto:4,na:4,name:[5,7,11,12],namespac:7,nb:5,nbamp:5,nbcol:5,nbofconnectedpc:5,nboftechniqu:5,nbparam:5,nbrow:5,nbset:5,neccessari:12,necessari:4,need:[10,11],netmask:5,never:12,new_ip:5,nfunction:11,nm_format:5,no_error:5,noerror:5,none:[0,1,2,3,4,5,7],note:5,noth:[5,7],npv:5,nrow:[4,6],ns:4,num:5,number:[4,5],numberofchannel:5,numberofslot:5,numer:[4,5,6],nwith:11,obj:5,object:[5,8,11],ocv:[4,5],oem:5,old:5,onc:12,one:[5,7,12],onli:[4,5,7,11,12],onto:12,open:7,open_circuit_voltag:[4,11],open_in:5,oper:13,opt_10a5v_badpow:5,opt_10a5v_err:5,opt_10a5v_error:5,opt_10a5v_overtemp:5,opt_10a5v_ovrtemp:5,opt_10a5v_powerfail:5,opt_10a5v_powfail:5,opt_1a48vp_badpow:5,opt_1a48vp_error:5,opt_1a48vp_overtemp:5,opt_1a48vp_powerfail:5,opt_48v:5,opt_48v_badpow:5,opt_48v_error:5,opt_48v_overtemp:5,opt_48v_ovrtemp:5,opt_48v_powerfail:5,opt_48v_powfail:5,opt_4a:5,opt_4a_badpow:5,opt_4a_error:5,opt_4a_overtemp:5,opt_4a_ovrtemp:5,opt_4a_powerfail:5,opt_4a_powfail:5,opt_chang:5,opt_open_in:5,opterr:5,option:[4,5,7,10,11],option_error:5,optionerror:5,optpo:5,order:[4,6],ordin:5,organis:[11,12],other_nam:7,otherwis:5,our:5,out:[11,12],output:[7,11],over:5,overal:[11,12],overflow:5,overheat:5,overriden:5,overwrit:4,overwritten:12,pa:4,packag:[4,9,10,11,12],pad_step:4,param:[4,5],param_boolean:5,param_int:5,param_singl:5,param_typ:5,paramet:[0,3,5,7],paramindex:5,paramstr:5,paramtyp:5,paramv:5,parm:5,pars:11,parse_raw_data:4,pass:6,path:[3,4,5,6,7,11],paus:5,payload:[3,4,6,7,12],payload_0_2:11,payload_to_ecc:4,pb:9,pc:12,pd:13,pdf:5,pdp:5,pdyn:5,pdynlimit:5,pei:5,perform:7,period:12,peter:[4,6,7,9,13],pid:[2,7],piec:11,pip:[2,10],pipelin:[0,1,3,7,12],pipeline_assign_job:2,pipeline_eject_sampl:2,pipeline_get_al:2,pipeline_get_info:2,pipeline_get_run:2,pipeline_insert:2,pipeline_load_sampl:2,pipeline_remov:2,pipeline_reset_job:2,place:12,plain:5,platform:10,pluggedchannel:5,pod:5,point:[4,5,11],poll:11,pollrat:11,possibl:12,potentiostat:[0,3,5,6,9,11],potpuls:5,power:5,pp_plural:5,pparam:5,pre:10,predic:5,prefix:[3,11],prematur:12,prepar:11,prepend:5,prepend_path:5,presenc:5,present:[7,11],preset:3,print:5,print_experiment_data:5,proce:12,process:12,process_yadg_preset:3,processindex:5,prog_stat:5,progress:5,prone:5,properti:[5,11],protocol:[4,6],provid:[4,5,7,11,12],ps:11,psp:5,pstr:2,pure:5,purpos:[5,6],pydant:11,pypi:10,pytest:10,python:5,pzir:5,q:[7,12],queri:[7,11],queu:7,queue:[3,6,7,9,11,12],queue_payload:2,queue_setup:2,quick:[9,12],quiet:7,qw:12,r:[7,12],rais:[5,7],ramsiz:5,random:6,rang:4,rate:4,raw:[11,12],rcomp:5,rd:[7,12],reach:[4,5],read:5,read_param_fail:5,readi:[2,4,6,7,12],rebind:5,recommend:10,record:5,record_every_d:4,record_every_di:4,record_every_dt:4,ref:11,refer:5,regist:5,relat:6,releas:13,reli:5,remain:12,remov:7,replac:11,repositori:10,repres:12,reproduc:5,request:[5,7],requir:[4,5,10,11],respect:10,respons:5,restyp:5,result:12,resultsarrai:5,rnpv:5,root:3,run:[4,5,6,7,10,11,12],run_ketchup:0,run_tomato:0,runtim:[4,6],runtimeerror:5,s:[4,5,7,11],sai:5,same:[5,11,12],sampl:[7,11,12],samplefil:11,sampleid:[2,7],samplenam:[7,12],satur:5,scan_rat:4,schedul:[9,12],schema:11,search:7,second:11,section:[12,13],see:[4,6,9,11,12],select:[5,12],separ:10,sequenc:11,sequenti:6,serial:5,server:5,set:[1,3,4,5,7,9,12],setethernetconfig:5,sethardwareconf:5,setlib:[0,11],setpoint:4,sever:5,sge:9,sgei:5,shield:5,shorthand:11,should:[5,7,10,11],show:[5,11],shown:11,side:5,sign:4,similar:11,simpl:5,singl:[7,11,12],size:5,snapshot:[3,7,11],so:12,socket_read:5,socket_writ:5,sp100:5,sp150:5,sp150e:5,sp200:5,sp240:5,sp300:5,sp50:5,sp50e:5,space:4,specif:[4,11],specifi:[4,6,7,11,12],spei:5,sqlite3:[0,2,9,11],sqlite:[2,7],st:2,stackgdyn:5,stackgdyn_slav:5,stackgei:5,stackgeis_slav:5,stackpdyn:5,stackpdyn_slav:5,stackpei:5,stackpeis_slav:5,stakehold:13,standard:5,start:[4,6,9],start_job:[4,6],startchannel:5,starttim:5,state:[5,7,11,12],state_setup:2,statu:[4,5,6,7,12],status:12,stop:[4,5,6],stop_job:[4,6],stopchannel:5,storag:11,store:11,str:[4,5,6,8],string:[5,11],strongli:10,structur:5,studi:4,style:5,submiss:7,submit:[4,7,12],subsequ:12,subset:5,successfulli:[11,12],suit:[10,12],suitabl:12,supervis:11,suppli:[7,11],support:[0,3,5,11,13],suppos:7,sweep:4,sweep_curr:[4,11],sweep_voltag:[4,11],swv:5,sync:5,sync_pipelines_to_st:0,syntax:11,system:12,t:[7,12],tabl:[11,13],tag:11,target:10,target_ip:5,tcol:2,tcp:5,tech:4,tech_datacorrupt:5,tech_eccfilecorrupt:5,tech_eccfilenotexist:5,tech_id:5,tech_incompatibleecc:5,tech_loadtechniquefail:5,tech_memful:5,tech_typ:5,technam:4,techniqu:[3,5,11,12],technique_info:5,techniqueid:5,techniqueindex:5,techniqueinfo:5,temperatur:5,templat:5,test:[1,4,7,12],testcomspe:5,testconnect:5,testmod:8,text:5,theo:13,therefor:[10,11],thi:[4,5,6,10,11,12],though:7,thought:11,ti:5,time:[4,6,12],timebas:5,timeout:5,timestamp:[4,6,12],titl:11,to_payload:11,tomato:[4,6,10,11],tomato_job:3,toml:11,too:5,total:[4,6],track:12,transcript:5,transfer:5,translat:[4,5],tupl:[2,4,5,6],turn:5,twin:[11,12],two:[11,12],type:[0,1,2,3,4,5,6,7,8,11],type_:5,ua:4,uncertainti:12,union:[4,5,6],unit:12,unknown:5,unknown_error:5,unless:[5,12],unlock:11,unlock_when_don:11,unpack:5,unplug:5,until:12,up:[7,12],updat:5,updateparamet:5,us:[4,5,6,9,10,11],usag:[7,9],usb:5,usb_devic:5,usb_deviceinfo:5,user:[5,11,12],user_config_dir:8,user_data_dir:8,user_log_dir:8,utf8:5,util:[5,9],v0:9,v:[4,7],val:4,valid:11,valu:[5,6,11],variabl:4,venv:10,verbos:[5,7,11,12],version:[5,11],versu:5,vi:5,vlimit:4,vmp2:5,vmp300:5,vmp3:5,vmp3e:5,vmp:5,voltag:3,vs:5,vsp300:5,vsp3e:5,vsp:5,vv:[10,11,12],wa:[7,12],wai:[11,12],wait:[5,12],warn:[7,11,12],warn_diff:5,we:[10,11],we_to_gnd:5,well:[11,12],what:5,wheel:10,when:[4,5,11],where:[4,11,12],whether:[5,7],which:[5,7,11,12],whole:5,window:[4,11],wintyp:5,within:[10,11,12],without:12,word:5,work:[7,10],worker:11,worri:12,wrap:5,wrapper:4,write:[5,6,11],xilinxvers:5,yadg:12,yadg_func:3,yaml:[7,11,12],yamlpath:8,yml:[7,11],you:[10,11],zboard:5,zero:4,zip:[7,12],zra:5},titles:["tomato package","tomato.daemon package","tomato.dbhandler package","tomato.drivers package","<strong>biologic</strong>: Driver for BioLogic potentiostats","tomato.drivers.biologic.kbio package","<strong>dummy</strong>: A dummy driver module","tomato.ketchup package","tomato.setlib package","<strong>tomato</strong>: au-tomation without the pain!","Installation","Quick start guide","Usage","<strong>tomato</strong>-v0.2"],titleterms:{"2":13,"final":12,A:6,access:12,au:9,biolog:[4,5],command:7,configur:4,control:4,current:4,daemon:[1,12],data:12,dbhandler:2,devic:11,driver:[3,4,5,6,9],dummi:6,file:11,first:11,gener:4,guid:11,instal:10,interfac:7,job:12,kbio:5,ketchup:[7,12],librari:9,limit:4,line:7,loop:4,manual:9,method:[4,6],modul:6,output:12,packag:[0,1,2,3,5,7,8],pain:9,paramet:[4,6],payload:11,pipelin:11,potentiostat:4,quick:11,section:11,set:11,setlib:8,snapshot:12,start:[11,12],submodul:[0,1,2,3,4,5,6,7,8],subpackag:[0,3,4],support:[4,6],techniqu:[4,6],test:10,time:11,tomat:9,tomato:[0,1,2,3,5,7,8,9,12,13],up:11,us:12,usag:12,user:9,v0:13,voltag:4,without:9}})