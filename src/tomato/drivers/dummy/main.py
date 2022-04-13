import logging
import random

log = logging.getLogger(__name__)
from datetime import datetime, timezone


def get_status(
    address: str,
    channel: int,
    **kwargs: dict,
) -> tuple[float, dict]:
    """
    Get the current status of the device.

    Parameters
    ----------
    address
        Not used

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
    dt = datetime.now(timezone.utc)
    return dt.timestamp(), True, {}


def get_data(
    address: str,
    channel: int,
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
    dt = datetime.now(timezone.utc)
    npoints = random.randint(0, channel)
    points = []
    for i in range(npoints):
        points.append({"value": random.random() * 100})
    data = {"data": points}
    return dt.timestamp(), npoints, data


def start_job(
    address: str,
    channel: int,
    **kwargs: dict,
) -> float:
    """
    Start a job on the device.

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
    dt = datetime.now(timezone.utc)
    return dt.timestamp()


def stop_job(
    address: str,
    channel: int,
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
    dt = datetime.now(timezone.utc)
    return dt.timestamp()
