import logging
import multiprocessing
import time

from datetime import datetime, timezone

from .kbio import kbio_types as KBIO
from .kbio_wrapper import (
    KBIO_api_wrapped,
    get_kbio_techpath,
    payload_to_ecc,
    parse_raw_data,
)

# number of attempts to perform a given operation before giving up
N_ATTEMPTS = 120

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
    logger.debug(f"starting get_status for '{address}:{channel}'")
    metadata = {}
    for attempt in range(N_ATTEMPTS):
        try:
            time0 = time.time()
            logger.debug(f"connecting to '{address}:{channel}'")
            with KBIO_api_wrapped(dllpath,address) as api:
                metadata["dll_version"] = api.GetLibVersion()
                id_, device_info = api.id_, api.device_info
                logger.info(f"getting status of '{address}:{channel}'")
                channel_info = api.GetChannelInfo(id_, channel)
            logger.debug(f"disconnected from '{address}:{channel}'")
            elapsed_time = time.time() - time0
            if elapsed_time > 0.5:
                logger.debug(f"status retrieved in {elapsed_time:.3f} s")
            if getattr(channel_info, "FirmwareVersion")==0:
                logger.debug(f"Attempt {attempt+1} failed: Firmware version read as 0")
            else:
                break
        except Exception as e:
            logger.debug(f"Attempt {attempt+1} failed: {e=}")
            if attempt == N_ATTEMPTS-1:
                logger.critical(f"Failed to get status after {N_ATTEMPTS} attempts, last error: {e}")
    metadata["device_model"] = device_info.model
    metadata["device_channels"] = device_info.NumberOfChannels
    metadata["channel_state"] = channel_info.state
    metadata["channel_board"] = channel_info.board
    metadata["mem_size"] = getattr(channel_info, "MemSize")
    metadata["channel_amp"] = channel_info.amplifier if channel_info.NbAmps else None
    metadata["channel_I_ranges"] = [channel_info.min_IRange, channel_info.max_IRange]
    logger.debug("Logging all channel info:")
    for field,_ in channel_info._fields_:
        logger.debug(f"{field}={getattr(channel_info,field)}")
    if metadata["channel_state"] in {"STOP"}:
        logger.debug("Channel state is 'STOP'")
        ready = True
    elif metadata["channel_state"] in {"RUN"}:
        logger.debug("Channel state is 'RUN'")
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
    logger.debug(f"starting get_data for '{address}:{channel}'")
    for attempt in range(N_ATTEMPTS):
        try:
            logger.debug(f"connecting to '{address}:{channel}'")
            time0 = time.time()
            with KBIO_api_wrapped(dllpath,address) as api:
                id_, device_info = api.id_, api.device_info
                logger.info(f"getting data from '{address}:{channel}'")
                data = api.GetData(id_, channel)
                data = parse_raw_data(api, data, device_info.model)
            logger.debug(f"disconnected from '{address}:{channel}'")
            elapsed_time = time.time() - time0
            if elapsed_time > 0.5:
                logger.debug(f"data retrieved in {elapsed_time:.3f} s")
            break
        except Exception as e:
            logger.debug(f"Attempt {attempt+1} failed: {e=}")
            if attempt == N_ATTEMPTS-1:
                logger.critical(f"Failed to get data after {N_ATTEMPTS} attempts, last error: {e}")
    dt = datetime.now(timezone.utc)
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
    logger.debug(f"starting start_job for '{address}:{channel}'")
    for attempt in range(N_ATTEMPTS):
        try:
            time0 = time.time()
            logger.debug(f"connecting to '{address}:{channel}'")
            with KBIO_api_wrapped(dllpath,address) as api:
                id_, device_info = api.id_, api.device_info
                logger.debug("translating payload to ECC")
                eccpars = payload_to_ecc(api, payload, capacity)
                ntechs = len(eccpars)
                first = True
                last = False
                ti = 1
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
                elapsed_time = time.time() - time0
                if elapsed_time > 0.5:
                    logger.debug(f"run started in {elapsed_time:.3f} s")
            logger.debug(f"disconnected from '{address}:{channel}'")
            break
        except Exception as e:
            logger.debug(f"Attempt {attempt+1} failed: {e=}")
            if attempt == N_ATTEMPTS-1:
                logger.critical(f"Failed to start job after {N_ATTEMPTS} attempts, last error: {e}")
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
    logger.debug(f"starting stop_job for '{address}:{channel}'")
    for attempt in range(N_ATTEMPTS):
        try:
            logger.debug(f"connecting to '{address}:{channel}'")
            with KBIO_api_wrapped(dllpath,address) as api:
                time0 = time.time()
                id_, device_info = api.id_, api.device_info
                logger.info(f"stopping run on '{address}:{channel}'")
                api.StopChannel(id_, channel)
            logger.debug(f"disconnected from '{address}:{channel}'")
            elapsed_time = time.time() - time0
            if elapsed_time > 0.5:
                logger.debug(f"run stopped in {elapsed_time:.3f} s")
            break
        except Exception as e:
            logger.debug(f"Attempt {attempt+1} failed: {e=}")
            if attempt == N_ATTEMPTS-1:
                logger.critical(f"Failed to stop job after {N_ATTEMPTS} attempts, last error: {e}")

    if jobqueue:
        jobqueue.close()
    else:
        pass
    dt = datetime.now(timezone.utc)
    logger.info(f"run stopped at '{dt}'")
    return dt.timestamp()
