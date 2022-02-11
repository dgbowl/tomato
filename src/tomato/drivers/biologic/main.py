
import logging
log = logging.getLogger(__name__)

from .kbio.kbio_api import KBIO_api
from .kbio_wrapper import payload_to_dsl, parse_raw_data


def get_status(
    address: str,
    channel: int,
    dllpath: str,
) -> tuple:

    api = KBIO_api(dllpath)
    version = api.GetLibVersion()
    id_, device_info = api.Connect(address)
    channel_info = api.GetChannelInfo(id_, channel)
    api.Disconnect(id_)
    return version, device_info, channel_info


def get_data(
    address: str,
    channel: int,
    dllpath: str,
) -> list:

    api = KBIO_api(dllpath)
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
    return



pl = [
    {
        "name": "OCV", "time": 3600, "record_every_dt": 10
    },
    {
        "name": "CPLIMIT", 
        "current": 0.01, 
        "time": 3600, 
        "limit_voltage_max": 4.2, 
        "I_range": "100 mA"
    },
    {
        "name": "CALIMIT", 
        "voltage": 4.2, 
        "time": 3600, 
        "limit_current_min": 0.001
    },
]

print(payload_to_dsl(pl))