
import logging
import time
log = logging.getLogger(__name__)

from .kbio_wrapper import (
    get_kbio_techpath,
    payload_to_ecc, 
    parse_raw_data, 
    get_kbio_api,
)


def get_status(address: str, channel: int, dllpath: str) -> tuple:
    """
    
    """
    api = get_kbio_api(dllpath)
    version = api.GetLibVersion()
    id_, device_info = api.Connect(address)
    channel_info = api.GetChannelInfo(id_, channel)
    api.Disconnect(id_)
    return version, device_info, channel_info


def get_data(address: str, channel: int, dllpath: str) -> list:
    """
    
    """
    api = get_kbio_api(dllpath)
    id_, device_info = api.Connect(address)
    data = api.GetData(id_, channel)
    api.Disconnect(id_)
    parsed_data = parse_raw_data(api, data, device_info.model)
    return parsed_data


def start_job(
    address: str,
    channel: int,
    dllpath: str,
    payload: list[dict]
) -> None:
    api = get_kbio_api(dllpath)
    eccpars = payload_to_ecc(api, payload)
    ntechs = len(eccpars)
    first = True
    last = False
    ti = 1
    id_, device_info = api.Connect(address)
    for techname, eccpars in eccpars:
        if ti == ntechs:
            last = True
        techfile = get_kbio_techpath(dllpath, techname, device_info.model)
        api.LoadTechnique(id_, channel, techfile, eccpars, first=first, last=last, display=True)
        ti += 1
        first = False
    api.StartChannel(id_, channel)
    api.Disconnect(id_)


def stop_job(address: str, channel: int, dllpath: str) -> None:
    """

    """
    api = get_kbio_api(dllpath)
    id_, device_info = api.Connect(address)
    api.StopChannel(id_, channel)
    api.Disconnect(id_)


