from abc import ABCMeta, abstractmethod
from typing import TypeVar, Any
from pydantic import BaseModel
from threading import Thread, currentThread
from queue import Queue
from tomato.models import Reply
from dgbowl_schemas.tomato.payload import Task
import logging
from functools import wraps
from xarray import Dataset
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


def in_devmap(func):
    @wraps(func)
    def wrapper(self, **kwargs):
        address = kwargs.get("address")
        channel = kwargs.get("channel")
        if (address, channel) not in self.devmap:
            msg = f"dev with address {address!r} and channel {channel} is unknown"
            return Reply(success=False, msg=msg, data=self.devmap.keys())
        return func(self, **kwargs)

    return wrapper


T = TypeVar("T")


class Attr(BaseModel):
    """Class used to describe device attributes."""

    type: T
    rw: bool = False
    status: bool = False


class DriverInterface(metaclass=ABCMeta):
    version: str = "1.0"

    class DeviceInterface(metaclass=ABCMeta):
        driver: object
        data: dict[str, list]
        key: tuple
        thread: Thread
        task_list: Queue
        running: bool

        def __init__(self, driver, key, **kwargs):
            self.driver = driver
            self.key = key
            self.task_list = Queue()
            self.thread = Thread(target=self.task_runner, daemon=True)
            self.data = defaultdict(list)
            self.running = False

        def run(self):
            self.thread.do_run = True
            self.thread.start()
            self.running = True

        def task_runner(self):
            thread = currentThread()
            task: Task = self.task_list.get()
            self.prepare_task(task)
            t0 = time.perf_counter()
            tD = t0
            self.data = defaultdict(list)
            while getattr(thread, "do_run"):
                tN = time.perf_counter()
                if tN - tD > task.sampling_interval:
                    self.do_task(task, t0=t0, tN=tN, tD=tD)
                    tD += task.sampling_interval
                if tN - t0 > task.max_duration:
                    break
                time.sleep(max(1e-2, task.sampling_interval / 10))

            self.task_list.task_done()
            self.running = False
            self.thread = Thread(target=self.task_runner, daemon=True)

        def prepare_task(self, task: Task, **kwargs: dict):
            for k, v in task.technique_params.items():
                self.set_attr(attr=k, val=v)

        @abstractmethod
        def do_task(self, task: Task, **kwargs: dict):
            pass

        def stop_task(self, **kwargs: dict):
            setattr(self.thread, "do_run", False)

        @abstractmethod
        def set_attr(self, attr: str, val: Any, **kwargs: dict):
            pass

        @abstractmethod
        def get_attr(self, attr: str, **kwargs: dict) -> Any:
            pass

        def get_data(self, **kwargs: dict) -> dict[str, list]:
            ret = self.data
            self.data = defaultdict(list)
            return ret

        @abstractmethod
        def attrs(**kwargs) -> dict:
            pass

        @abstractmethod
        def tasks(**kwargs) -> set:
            pass

        def status(self, **kwargs) -> dict:
            status = {}
            for attr, props in self.attrs().items():
                if props.status:
                    status[attr] = self.get_attr(attr)
            return status

    def CreateDeviceInterface(self, key, **kwargs):
        """Factory function which passes DriverInterface to the DeviceInterface"""
        return self.DeviceInterface(self, key, **kwargs)

    devmap: dict[tuple, DeviceInterface]
    """Map of registered devices, the tuple keys are components = (address, channel)"""

    settings: dict[str, Any]
    """A settings map to contain driver-specific settings such as `dllpath` for BioLogic"""

    def __init__(self, settings=None):
        self.devmap = {}
        self.settings = settings if settings is not None else {}

    def dev_register(self, address: str, channel: int, **kwargs: dict) -> None:
        """
        Register a Device and its Component in this DriverInterface, creating a
        :obj:`self.DeviceInterface` object in the :obj:`self.devmap` if necessary, or
        updating existing channels in :obj:`self.devmap`.
        """
        key = (address, channel)
        self.devmap[key] = self.CreateDeviceInterface(key, **kwargs)

    def dev_teardown(self, address: str, channel: int, **kwargs: dict) -> None:
        """
        Emergency stop function. Set the device into a documented, safe state.

        The function is to be only called in case of critical errors, not as part of
        normal operation.
        """
        pass

    @in_devmap
    def attrs(self, address: str, channel: int, **kwargs) -> Reply | None:
        key = (address, channel)
        ret = self.devmap[key].attrs(**kwargs)
        return Reply(
            success=True,
            msg=f"attrs of component {key} are: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_set_attr(
        self, attr: str, val: Any, address: str, channel: int, **kwargs
    ) -> Reply | None:
        key = (address, channel)
        self.devmap[key].set_attr(attr=attr, val=val, **kwargs)
        return Reply(
            success=True,
            msg=f"attr {attr!r} of component {key} set to {val}",
            data=val,
        )

    @in_devmap
    def dev_get_attr(
        self, attr: str, address: str, channel: int, **kwargs
    ) -> Reply | None:
        key = (address, channel)
        ret = self.devmap[key].get_attr(attr=attr, **kwargs)
        return Reply(
            success=True,
            msg=f"attr {attr!r} of component {key} is: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_status(self, address: str, channel: int, **kwargs) -> Reply | None:
        key = (address, channel)
        running = self.devmap[key].running
        return Reply(
            success=True,
            msg=f"component {key} is{' ' if running else ' not ' }running",
            data=running,
        )

    @in_devmap
    def task_start(
        self, address: str, channel: int, task: Task, **kwargs
    ) -> Reply | None:
        key = (address, channel)
        if task.technique_name not in self.devmap[key].tasks(**kwargs):
            return Reply(
                success=False,
                msg=f"unknown task {task.technique_name!r} requested",
                data=self.tasks(address=address, channel=channel),
            )

        key = (address, channel)
        self.devmap[key].task_list.put(task)
        self.devmap[key].run()
        return Reply(
            success=True,
            msg=f"task {task!r} started successfully",
            data=task,
        )

    @in_devmap
    def task_status(self, address: str, channel: int):
        key = (address, channel)
        started = self.devmap[key].running
        if not started:
            return Reply(success=True, msg="ready")
        else:
            return Reply(success=True, msg="running")

    @in_devmap
    def task_stop(self, address: str, channel: int, **kwargs) -> Reply | None:
        key = (address, channel)
        ret = self.devmap[key].stop_task(**kwargs)
        if ret is not None:
            return Reply(success=False, msg="failed to stop task", data=ret)

        ret = self.task_data(self, address, channel)
        if ret.success:
            return Reply(success=True, msg=f"task stopped, {ret.msg}", data=ret.data)
        else:
            return Reply(success=True, msg=f"task stopped, {ret.msg}")

    @in_devmap
    def task_data(self, address: str, channel: int, **kwargs) -> Reply | None:
        key = (address, channel)
        data = self.devmap[key].get_data(**kwargs)

        if len(data) == 0:
            return Reply(success=False, msg="found no new datapoints")

        uts = {"uts": data.pop("uts")}
        data = {k: ("uts", v) for k, v in data.items()}
        ds = Dataset(data_vars=data, coords=uts)
        return Reply(success=True, msg=f"found {len(data)} new datapoints", data=ds)

    def status(self):
        devkeys = self.devmap.keys()
        return Reply(
            success=True,
            msg=f"driver running with {len(devkeys)} devices",
            data=dict(devkeys=devkeys),
        )

    def teardown(self):
        for key, dev in self.devmap.items():
            dev.thread.do_run = False
            dev.thread.join(1)
            if dev.thread.is_alive():
                logger.error(f"device {key!r} is still alive")
            else:
                logger.debug(f"device {key!r} successfully closed")

    def dev_get_data(self, address: str, channel: int, **kwargs):
        ret = {}
        for k in self.attrs(address=address, channel=channel, **kwargs).keys():
            ret[k] = self.dev_get_attr(
                attr=k, address=address, channel=channel, **kwargs
            )
        return ret

    def tasks(self, address: str, channel: int, **kwargs) -> dict:
        key = (address, channel)
        ret = self.devmap[key].tasks(**kwargs)
        return Reply(
            success=True,
            msg=f"tasks supported by component {key} are: {ret}",
            data=ret,
        )
