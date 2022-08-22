import logging
import random
import time
import multiprocessing

from datetime import datetime, timezone


def _dummy_process(
    queue: multiprocessing.Queue,
    tech: str = "random",
    delay: int = 1,
    t: int = 10,
) -> None:
    ts = te = time.perf_counter()
    nd = 0
    while te - ts < t:
        if queue.empty():
            queue.put(None)
        if te >= ts + nd * delay:
            nd += 1
            if tech == "random":
                data = {
                    "time": te - ts,
                    "value": random.random(),
                }
            elif tech == "sequential":
                data = {
                    "time": te - ts,
                    "value": nd,
                }
            else:
                raise RuntimeError(f"technique '{tech}' not understood.")
            queue.put(data)
        time.sleep(1e-3)
        te = time.perf_counter()
    return


def get_status(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
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
    logger.debug("in 'dummy.get_status'")
    dt = datetime.now(timezone.utc)
    metadata = {"address": address, "channel": channel}
    if jobqueue:
        ready = jobqueue.empty()
    else:  # this happens when called by driver_reset
        ready = True
    return dt.timestamp(), ready, metadata


def get_data(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
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
    logger.debug(
        f"in 'dummy.get_data', jobqueue is{'' if jobqueue.empty() else ' not'} empty"
    )
    dt = datetime.now(timezone.utc)
    points = []
    while not jobqueue.empty():
        v = jobqueue.get()
        if isinstance(v, dict):
            points.append(v)
    if jobqueue.empty() and len(points) > 0:
        jobqueue.put(None)
    npoints = len(points)
    data = {"data": points, "current": None}
    return dt.timestamp(), npoints, data


def start_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: logging.Logger,
    payload: list[dict],
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

    jobqueue
        :class:`multiprocessing.Queue` for passing job related data.

    logger
        :class:`logging.Logger` instance for writing logs.

    payload
        A protocol describing the techniques to be executed and their order.

    Returns
    -------
    timestamp
        A timestamp corresponding to the start of the job execution.

    """
    dt = datetime.now(timezone.utc)
    logger.info("in 'dummy.start_job'")
    logger.debug(f"{payload=}")
    for ip, p in enumerate(payload):
        delay = p.get("delay", 1)
        t = p.get("time", 10)
        tech = p["technique"]
        logger.debug(
            f"starting 'dummy._dummy_process' {ip} with {tech=}, {t=}, {delay=}."
        )
        pr = multiprocessing.Process(
            target=_dummy_process, args=(jobqueue, tech, delay, t)
        )
        pr.start()
    # Delay before quitting so that processes get a chance to start
    time.sleep(1)
    return dt.timestamp()


def stop_job(
    address: str,
    channel: int,
    jobqueue: multiprocessing.Queue,
    logger: multiprocessing.Queue,
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
    if jobqueue:
        jobqueue.close()
    else:
        pass
    dt = datetime.now(timezone.utc)
    return dt.timestamp()
