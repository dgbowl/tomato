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
    logger.debug("starting get_status for '%s:%s'", address, channel)
    metadata = {}
    for attempt in range(N_ATTEMPTS):
        try:
            time0 = time.perf_counter()
            with KBIO_api_wrapped(dllpath, address) as api:
                metadata["dll_version"] = api.GetLibVersion()
                id_, device_info = api.id_, api.device_info
                logger.info("getting status of '%s:%s'", address, channel)
                channel_info = api.GetChannelInfo(id_, channel)
            elapsed_time = time.perf_counter() - time0
            if elapsed_time > 0.5:
                logger.debug("status retrieved in %.3f s", elapsed_time)
            if getattr(channel_info, "FirmwareVersion") == 0:
                logger.debug(
                    "Attempt %d failed: Firmware version read as 0", attempt + 1
                )
            else:
                break
        except Exception as e:
            logger.debug("Attempt %d failed: %s", attempt + 1, e)
            if attempt == N_ATTEMPTS - 1:
                logger.critical(
                    "Failed to start job after %d attempts, last error: %s",
                    N_ATTEMPTS,
                    e,
                )
            raise e
    metadata["device_model"] = device_info.model
    metadata["device_channels"] = device_info.NumberOfChannels
    metadata["channel_state"] = channel_info.state
    metadata["channel_board"] = channel_info.board
    metadata["mem_size"] = getattr(channel_info, "MemSize")
    metadata["channel_amp"] = channel_info.amplifier if channel_info.NbAmps else None
    metadata["channel_I_ranges"] = [channel_info.min_IRange, channel_info.max_IRange]
    logger.debug("Logging all channel info:")
    for field, _ in channel_info._fields_:
        logger.debug("%s=%s", field, getattr(channel_info, field))
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
    logger.debug("starting get_data for '%s:%s'", address, channel)
    time0 = time.perf_counter()
    for attempt in range(N_ATTEMPTS):
        try:
            with KBIO_api_wrapped(dllpath, address) as api:
                id_, device_info = api.id_, api.device_info
                logger.debug("getting data from '%s:%s'", address, channel)
                data = api.GetData(id_, channel)
                data = parse_raw_data(api, data, device_info.model)
            break
        except Exception as e:
            logger.debug("Attempt %d failed: %s", attempt + 1, e)
            if attempt == N_ATTEMPTS - 1:
                logger.critical(
                    "Failed to start job after %d attempts, last error: %s",
                    N_ATTEMPTS,
                    e,
                )
            raise e
    dt = datetime.now(timezone.utc)
    nrows = data["technique"]["data_rows"]
    elapsed_time = time.perf_counter() - time0
    logger.info(
        "read %d rows from '%s:%s' in %d attempts in %.3f s",
        nrows,
        address,
        channel,
        attempt + 1,
        elapsed_time,
    )
    return dt.timestamp(), nrows, data


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
    logger.debug("starting start_job for '%s:%s'", address, channel)
    for attempt in range(N_ATTEMPTS):
        try:
            time0 = time.perf_counter()
            with KBIO_api_wrapped(dllpath, address) as api:
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
                    logger.info("loading technique %d: '%s'", ti, techname)
                    api.LoadTechnique(
                        id_,
                        channel,
                        techfile,
                        pars,
                        first=first,
                        last=last,
                        display=False,
                    )
                    ti += 1
                    first = False
                logger.info("starting run on '%s:%s'", address, channel)
                api.StartChannel(id_, channel)
                elapsed_time = time.perf_counter() - time0
                if elapsed_time > 0.5:
                    logger.debug("run started in %.3f s", elapsed_time)
            break
        except Exception as e:
            logger.debug("Attempt %d failed: %s", attempt + 1, e)
            if attempt == N_ATTEMPTS - 1:
                logger.critical(
                    "Failed to start job after %d attempts, last error: %s",
                    N_ATTEMPTS,
                    e,
                )
            raise e
    dt = datetime.now(timezone.utc)
    logger.info("run started at '%s'", dt)
    return dt.timestamp()


def stop_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: multiprocessing.Queue,
    dllpath: str = None,
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
    logger.debug("starting stop_job for '%s:%s'", address, channel)
    for attempt in range(N_ATTEMPTS):
        try:
            with KBIO_api_wrapped(dllpath, address) as api:
                time0 = time.perf_counter()
                id_, device_info = api.id_, api.device_info
                logger.info("stopping run on '%s:%s'", address, channel)
                api.StopChannel(id_, channel)
            elapsed_time = time.perf_counter() - time0
            if elapsed_time > 0.5:
                logger.debug("run stopped in %.3f s", elapsed_time)
            break
        except Exception as e:
            logger.debug("Attempt %d failed: %s", attempt + 1, e)
            if attempt == N_ATTEMPTS - 1:
                logger.critical(
                    "Failed to start job after %d attempts, last error: %s",
                    N_ATTEMPTS,
                    e,
                )
            raise e

    if jobqueue:
        jobqueue.close()
    else:
        pass
    dt = datetime.now(timezone.utc)
    logger.info("run stopped at '%s'", dt)
    return dt.timestamp()
