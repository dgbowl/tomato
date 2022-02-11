
import logging
log = logging.getLogger(__name__)

from .kbio_wrapper import payload_to_dsl, parse_raw_data, get_kbio_api


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
    parsed_data = parse_raw_data(api, data)
    return parsed_data


def start_job(
    address: str,
    channel: int,
    dllpath: str,
    payload: list[dict]
) -> None:
    print(payload)


def stop_job(address: str, channel: int, dllpath: str) -> None:
    """

    """
    api = get_kbio_api(dllpath)
    id_, device_info = api.Connect(address)
    api.StopChannel(id_, channel)
    api.Disconnect(id_)



pl = [
    {
        "name": "OCV", "time": 3600, "record_every_dt": 10
    }
]

#print(payload_to_dsl(pl))