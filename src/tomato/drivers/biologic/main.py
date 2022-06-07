import logging
import multiprocessing

from datetime import datetime, timezone

from .kbio_wrapper import (
    get_kbio_techpath,
    payload_to_ecc,
    parse_raw_data,
    get_kbio_api,
)


def get_status(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    dllpath: str = None,
    **kwargs: dict,
) -> tuple[float, dict]:
    """
    Get the current status of the device.

    Parameters
    ----------
    address
        IP address of the potentiostat.

    channel
        Numeric, 1-indexed ID of the channel.

    dllpath
        Path to the BioLogic DLL file.

    Returns
    -------
    timestamp, ready, metadata: tuple[float, bool, dict]
        Returns a tuple containing the timestamp, readiness status, and
        associated metadata.

    """
    api = get_kbio_api(dllpath)
    metadata = {}
    metadata["dll_version"] = api.GetLibVersion()
    for t in range(0,10):
        try:
            logger.debug(f"connecting to '{address}:{channel}', try {t+1}")
            id_, device_info = api.Connect(address)
            channel_info = api.GetChannelInfo(id_, channel)
            dt = datetime.now(timezone.utc)
            logger.debug(f"disconnecting from '{address}:{channel}', try {t+1}")
            api.Disconnect(id_)
        except Exception as e:
            logger.critical(e)
        finally:
            if channel_info.state in {"STOP", "RUN"}:
                break
    metadata["device_model"] = device_info.model
    metadata["device_channels"] = device_info.NumberOfChannels
    metadata["channel_state"] = channel_info.state
    metadata["channel_board"] = channel_info.board
    metadata["channel_amp"] = channel_info.amplifier if channel_info.NbAmps else None
    metadata["channel_I_ranges"] = [channel_info.min_IRange, channel_info.max_IRange]
    if metadata["channel_state"] == ["STOP"]:
        ready = True
    else:
        ready = False
    return dt.timestamp(), ready, metadata


def get_data(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    dllpath: str = None,
    **kwargs: dict,
) -> tuple[float, dict]:
    """
    Get cached data from the device.

    Parameters
    ----------
    address
        IP address of the potentiostat.

    channel
        Numeric, 1-indexed ID of the channel.

    dllpath
        Path to the BioLogic DLL file.

    Returns
    -------
    timestamp, nrows, data: tuple[float, int, dict]
        Returns a tuple containing the timestamp and associated metadata.

    """
    api = get_kbio_api(dllpath)
    logger.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    logger.debug(f"getting data")
    data = api.GetData(id_, channel)
    dt = datetime.now(timezone.utc)
    logger.debug(f"disconnecting from '{address}:{channel}'")
    api.Disconnect(id_)
    data = parse_raw_data(api, data, device_info.model)
    return dt.timestamp(), data["technique"]["data_rows"], data


def start_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    payload: list[dict],
    dllpath: str = None,
    capacity: float = 0.0,
    **kwargs: dict,
) -> float:
    """
    Start a job on the device.

    The function first translates the ``payload`` into an instrument-specific
    language, using the ``capacity`` provided if necessary. The converted
    ``payload`` is then submitted to the device, overwriting any current job
    information.

    Parameters
    ----------
    address
        IP address of the potentiostat.

    channel
        Numeric, 1-indexed ID of the channel.

    dllpath
        Path to the BioLogic DLL file.

    payload
        A protocol describing the techniques to be executed and their order.

    capacity
        The capacity information for the studied battery cell. Only required for
        battery-testing applications or for payloads where currents are specified
        using C or D rates.

    Returns
    -------
    timestamp
        A timestamp corresponding to the start of the job execution.

    """
    api = get_kbio_api(dllpath)
    logger.debug("translating payload to ECC")
    eccpars = payload_to_ecc(api, payload, capacity)
    ntechs = len(eccpars)
    try:
        first = True
        last = False
        ti = 1
        logger.debug(f"connecting to '{address}:{channel}'")
        id_, device_info = api.Connect(address)
        for techname, pars in eccpars:
            if ti == ntechs:
                last = True
            techfile = get_kbio_techpath(dllpath, techname, device_info.model)
            logger.debug(f"loading technique {ti}: '{techname}'")
            api.LoadTechnique(
                id_, channel, techfile, pars, first=first, last=last, display=False
            )
            ti += 1
            first = False
        logger.debug(f"starting run on '{address}:{channel}'")
        api.StartChannel(id_, channel)
        dt = datetime.now(timezone.utc)
        logger.info(f"run started at '{dt}'")
        logger.debug(f"disconnecting from '{address}:{channel}'")
        api.Disconnect(id_)
    except Exception as e:
        logger.critical(e)
    return dt.timestamp()


def stop_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: multiprocessing.Queue,
    dllpath: str,
    **kwargs: dict,
) -> float:
    """
    Stop a job running on the device.

    This function stops any currently running technique on the specified channel
    of the device. No data is returned.

    Parameters
    ----------
    address
        IP address of the potentiostat.

    channel
        Numeric, 1-indexed ID of the channel.

    dllpath
        Path to the BioLogic DLL file.

    Returns
    -------
    timestamp
        A timestamp corresponding to the start of the job execution.

    """
    api = get_kbio_api(dllpath)
    logger.debug(f"connecting to '{address}:{channel}'")
    id_, device_info = api.Connect(address)
    logger.debug(f"stopping run on '{address}:{channel}'")
    api.StopChannel(id_, channel)
    dt = datetime.now(timezone.utc)
    logger.info(f"run stopped at '{dt}'")
    api.Disconnect(id_)
    jobqueue.close()
    return dt.timestamp()
