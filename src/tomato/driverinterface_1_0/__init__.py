from abc import ABCMeta, abstractmethod
from typing import TypeVar, Any, Literal
from pydantic import BaseModel
from threading import Thread, currentThread
from queue import Queue
from tomato.models import Reply
from dgbowl_schemas.tomato.payload import Task
import logging
from functools import wraps
from xarray import Dataset


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


class ModelInterface(metaclass=ABCMeta):
    version: Literal = "1.0"

    class Attr(BaseModel):
        """Class used to describe device attributes."""

        type: TypeVar("T")
        rw: bool = False
        status: bool = False

    class DeviceInterface(metaclass=ABCMeta):
        driver: object
        data: list
        status: dict
        key: tuple
        thread: Thread
        task_list: Queue
        running: bool

        def __init__(self, driver, key, **kwargs):
            self.driver = driver
            self.key = key
            self.task_list = Queue()
            self.thread = Thread(target=self._worker_wrapper, daemon=True)
            self.data = []
            self.status = {}
            self.running = False

        def run(self):
            self.thread.do_run = True
            self.thread.start()
            self.running = True

        def _worker_wrapper(self):
            thread = currentThread()
            task = self.task_list.get()

            self.task_runner(task, thread)

            self.task_list.task_done()
            self.running = False
            self.thread = Thread(target=self._worker_wrapper, daemon=True)

        @abstractmethod
        def task_runner(task: Task, thread: Thread):
            pass

    def CreateDeviceInterface(self, key, **kwargs):
        """Factory function which passes DriverInterface to the DeviceInterface"""
        return self.DeviceInterface(self, key, **kwargs)

    devmap: dict[tuple, DeviceInterface]
    """Map of registered devices, the tuple keys are components = (address, channel)"""

    settings: dict[str, str]
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
        self.devmap[(address, channel)] = self.CreateDeviceInterface(key, **kwargs)

    def dev_teardown(self, address: str, channel: int, **kwargs: dict) -> None:
        """
        Emergency stop function. Set the device into a documented, safe state.

        The function is to be only called in case of critical errors, not as part of
        normal operation.
        """
        pass

    @abstractmethod
    def attrs(self, address: str, channel: int, **kwargs) -> dict[str, Attr]:
        """
        Function that returns all gettable and settable attributes, their rw status,
        and whether they are to be returned in :func:`self.dev_status`. All attrs are
        returned by :func:`self.dev_get_data`.

        This is the "low level" control interface, intended for the device dashboard.

        Example:
            ::

                return dict(
                    delay = self.Attr(type=float, rw=True, status=False),
                    time = self.Attr(type=float, rw=True, status=False),
                    started = self.Attr(type=bool, rw=True, status=True),
                    val = self.Attr(type=int, rw=False, status=True),
                )

        """
        pass

    @in_devmap
    def dev_set_attr(self, attr: str, val: Any, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs():
            params = self.attrs()[attr]
            if params.rw and isinstance(val, params.type):
                self.devmap[key].status[attr] = val

    @in_devmap
    def dev_get_attr(self, attr: str, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs(address=address, channel=channel):
            return self.devmap[key].status[attr]

    @in_devmap
    def dev_status(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        running = self.devmap[key].running
        return Reply(
            success=True,
            msg=f"component {key} is{' ' if running else ' not ' }running",
            data=running,
        )

    @in_devmap
    def task_start(self, address: str, channel: int, task: Task, **kwargs):
        if task.technique_name not in self.tasks(address=address, channel=channel):
            return Reply(
                success=False,
                msg=f"unknown task {task.technique_name!r} requested",
                data=self.tasks(),
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
    def task_stop(self, address: str, channel: int):
        self.dev_set_attr(attr="started", val=False, address=address, channel=channel)

        ret = self.task_data(self, address, channel)
        if ret.success:
            return Reply(success=True, msg=f"task stopped, {ret.msg}", data=ret.data)
        else:
            return Reply(success=True, msg=f"task stopped, {ret.msg}")

    @in_devmap
    def task_data(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        data = self.devmap[key].data
        self.devmap[key].data = []

        if len(data) == 0:
            return Reply(success=False, msg="found no new datapoints")

        data_vars = {}
        for ii, item in enumerate(data):
            for k, v in item.items():
                if k not in data_vars:
                    data_vars[k] = [None] * ii
                data_vars[k].append(v)
            for k in data_vars:
                if k not in item:
                    data_vars[k].append(None)

        uts = {"uts": data_vars.pop("uts")}
        data_vars = {k: ("uts", v) for k, v in data_vars.items()}
        ds = Dataset(data_vars=data_vars, coords=uts)
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

    @abstractmethod
    def tasks(self, address: str, channel: int, **kwargs) -> dict:
        """
        Function that returns all tasks that can be submitted to the Device. This
        implements the driver specific language. Each task in tasks can only contain
        elements present in :func:`self.attrs`.

        Example:
            ::

                return dict(
                    count = dict(time = dict(type=float), delay = dict(type=float),
                )

        """
        pass
