
import logging
log = logging.getLogger(__name__)
from datetime import datetime, timezone

from .kbio_wrapper import (
    get_kbio_techpath,
    payload_to_ecc, 
    parse_raw_data, 
    get_kbio_api,
)


def get_status(address: str, channel: int, dllpath: str) -> tuple[float, dict]:
    """
    
    """
    api = get_kbio_api(dllpath)
    metadata = {}
    metadata["dll_version"] = api.GetLibVersion()
    log.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    metadata["device_model"] = device_info.model
    metadata["device_channels"] = device_info.NumberOfChannels
    channel_info = api.GetChannelInfo(id_, channel)
    dt = datetime.now(timezone.utc)
    metadata["channel_state"] = channel_info.state
    metadata["channel_board"] = channel_info.board
    metadata["channel_amp"] = channel_info.amplifier
    log.debug(f"disconnecting from '{address}:{channel}'")
    api.Disconnect(id_)
    return dt.timestamp(), metadata


def get_data(address: str, channel: int, dllpath: str) -> tuple[float, dict]:
    """
    
    """
    api = get_kbio_api(dllpath)
    log.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    log.debug(f"getting data")
    data = api.GetData(id_, channel)
    dt = datetime.now(timezone.utc)
    log.debug(f"disconnecting from '{address}:{channel}'")
    api.Disconnect(id_)
    data = parse_raw_data(api, data, device_info.model)
    return dt.timestamp(), data


def start_job(
    address: str,
    channel: int,
    dllpath: str,
    payload: list[dict],
    capacity: float
) -> float:
    api = get_kbio_api(dllpath)
    log.debug("translating payload to ECC")
    eccpars = payload_to_ecc(api, payload, capacity)
    ntechs = len(eccpars)
    first = True
    last = False
    ti = 1
    log.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    for techname, pars in eccpars:
        if ti == ntechs:
            last = True
        techfile = get_kbio_techpath(dllpath, techname, device_info.model)
        log.debug(f"loading technique {ti}: '{techname}'")
        api.LoadTechnique(id_, channel, techfile, pars, first=first, last=last, display=True)
        ti += 1
        first = False
    log.debug(f"starting run on '{address}:{channel}'")
    api.StartChannel(id_, channel)
    dt = datetime.now(timezone.utc)
    log.info(f"run started at '{dt}'")
    log.debug(f"disconnecting from '{address}:{channel}'")
    api.Disconnect(id_)
    return dt.timestamp()


def stop_job(address: str, channel: int, dllpath: str) -> float:
    """

    """
    api = get_kbio_api(dllpath)
    log.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    log.debug(f"stopping run on '{address}:{channel}'")
    api.StopChannel(id_, channel)
    dt = datetime.now(timezone.utc)
    log.info(f"run stopped at '{dt}'")
    api.Disconnect(id_)
    return dt.timestamp()


