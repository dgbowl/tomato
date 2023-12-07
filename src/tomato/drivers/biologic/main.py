import logging
import multiprocessing
import time
from filelock import FileLock
from datetime import datetime, timezone
from .kbio_wrapper import (
    get_kbio_techpath,
    payload_to_ecc,
    parse_raw_data,
    get_kbio_api,
)

def safe_api_connect(api,
                    address: str,
                    retries: int = 100,
                    timeout: int = 10
                    ) -> tuple:
    """
    Attempt to establish a connection with the device, retrying if necessary.

    This function attempts to connect to the device at the specified address.
    If the connection attempt fails, it retries up to a specified number of times,
    waiting for a specified timeout period between each attempt.

    Parameters
    ----------
    api
        The API object used for making the connection.
    address : str
        The IP address of the device to connect to.
    retries : int, optional
        The number of times to retry the connection attempt. Default is 100.
    timeout : int, optional
        The time in seconds to wait between retries. Default is 10.

    Returns
    -------
    tuple
        A tuple containing the ID and device information upon successful connection.

    Raises
    ------
    Exception
        If the function fails to connect after the specified number of retries.

    """
    for _ in range(retries):
        try:
            id_, device_info = api.Connect(address)
            return id_, device_info
        except Exception as e:
            time.sleep(timeout)
    raise Exception(f"Failed to connect after {retries} retries")


def safe_api_disconnect(api,
                        id_,
                        retries: int = 100,
                        timeout: int = 10):
    """
    Attempt to disconnect from the device, retrying if necessary.

    This function attempts to disconnect from the device using the provided ID.
    If the disconnection attempt fails, it retries up to a specified number of times,
    waiting for a specified timeout period between each attempt.

    Parameters
    ----------
    api
        The API object used for disconnecting.
    id_
        The ID of the device to disconnect from.
    retries : int, optional
        The number of times to retry the disconnection attempt. Default is 100.
    timeout : int, optional
        The time in seconds to wait between retries. Default is 10.

    Raises
    ------
    Exception
        If the function fails to disconnect after the specified number of retries.

    """
    for _ in range(retries):
        try:
            api.Disconnect(id_)
            return
        except Exception as e:
            time.sleep(timeout)
    raise Exception(f"Failed to disconnect after {retries} retries")



def get_status(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    dllpath: str = None,
    lockpath: str = None,
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
    with FileLock(lockpath, timeout=60) as fh:
        try:
            logger.info(f"connecting to '{address}:{channel}'")
            id_, device_info = safe_api_connect(api, address)
            logger.info(f"getting status of '{address}:{channel}'")
            channel_info = api.GetChannelInfo(id_, channel)
            logger.info(f"disconnecting from '{address}:{channel}'")
            safe_api_disconnect(api, id_)
        except Exception as e:
            logger.critical(f"{e=}")
            raise
    metadata["device_model"] = device_info.model
    metadata["device_channels"] = device_info.NumberOfChannels
    metadata["channel_state"] = channel_info.state
    metadata["channel_board"] = channel_info.board
    metadata["channel_amp"] = channel_info.amplifier if channel_info.NbAmps else None
    metadata["channel_I_ranges"] = [channel_info.min_IRange, channel_info.max_IRange]
    if metadata["channel_state"] in {"STOP"}:
        ready = True
    elif metadata["channel_state"] in {"RUN"}:
        ready = False
    else:
        logger.critical("channel state not understood: '%s'", metadata["channel_state"])
        raise ValueError("channel state not understood")
    dt = datetime.now(timezone.utc)
    return dt.timestamp(), ready, metadata

def get_data(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    dllpath: str = None,
    lockpath: str = None,
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
    with FileLock(lockpath, timeout=60) as fh:
        try:
            logger.info(f"connecting to '{address}:{channel}'")
            id_, device_info = safe_api_connect(api, address)
            logger.info(f"getting data from '{address}:{channel}'")
            data = api.GetData(id_, channel)
            logger.info(f"disconnecting from '{address}:{channel}'")
            safe_api_disconnect(api, id_)
        except Exception as e:
            logger.critical(f"{e=}")
            raise
    dt = datetime.now(timezone.utc)
    data = parse_raw_data(api, data, device_info.model)
    return dt.timestamp(), data["technique"]["data_rows"], data

def start_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    payload: list[dict],
    dllpath: str = None,
    lockpath: str = None,
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
    with FileLock(lockpath, timeout=60) as fh:
        try:
            first = True
            last = False
            ti = 1
            logger.info(f"connecting to '{address}:{channel}'")
            id_, device_info = safe_api_connect(api, address)
            for techname, pars in eccpars:
                if ti == ntechs:
                    last = True
                techfile = get_kbio_techpath(dllpath, techname, device_info.model)
                logger.info(f"loading technique {ti}: '{techname}'")
                api.LoadTechnique(
                    id_, channel, techfile, pars, first=first, last=last, display=False
                )
                ti += 1
                first = False
            logger.info(f"starting run on '{address}:{channel}'")
            api.StartChannel(id_, channel)
            logger.info(f"disconnecting from '{address}:{channel}'")
            safe_api_disconnect(api, id_)
        except Exception as e:
            logger.critical(f"{e=}")
            raise
    dt = datetime.now(timezone.utc)
    logger.info(f"run started at '{dt}'")
    return dt.timestamp()

def stop_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: multiprocessing.Queue,
    dllpath: str = None,
    lockpath: str = None,
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
    with FileLock(lockpath, timeout=60) as fh:
        try:
            logger.info(f"connecting to '{address}:{channel}'")
            id_, device_info = safe_api_connect(api, address)
            logger.info(f"stopping run on '{address}:{channel}'")
            api.StopChannel(id_, channel)
            logger.info(f"run stopped at '{dt}'")
            safe_api_disconnect(api, id_)
        except Exception as e:
            logger.critical(f"{e=}")
            raise
    if jobqueue:
        jobqueue.close()
    else:
        pass
    dt = datetime.now(timezone.utc)
    return dt.timestamp()
