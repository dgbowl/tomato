from abc import ABCMeta, abstractmethod
import xarray as xr
from typing import TypeVar, Any, Literal
from pydantic import BaseModel


class ModelInterface(metaclass=ABCMeta):
    version: Literal = "1.0"

    class Attr(BaseModel):
        """Class used to describe device attributes."""

        type: TypeVar("T")
        rw: bool = False
        status: bool = False

    class DeviceInterface(metaclass=ABCMeta):
        """Class used to implement management of each individual device."""

        pass

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
        self.devmap[(address, channel)] = self.DeviceInterface(**kwargs)

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

    @abstractmethod
    def dev_set_attr(self, attr: str, val: Any, address: str, channel: int, **kwargs):
        """Set the value of a read-write attr on a Component"""
        pass

    @abstractmethod
    def dev_get_attr(self, attr: str, address: str, channel: int, **kwargs):
        """Get the value of any attr from a Component"""
        pass

    def dev_status(self, address: str, channel: int, **kwargs) -> dict[str, Any]:
        """Get a status report from a Component"""
        ret = {}
        for k, v in self.attrs(address=address, channel=channel, **kwargs).items():
            if v.status:
                ret[k] = self.dev_get_attr(
                    attr=k, address=address, channel=channel, **kwargs
                )
        return ret

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

    @abstractmethod
    def task_start(self, address: str, channel: int, task: str, **kwargs) -> None:
        """start a task on a (ready) component"""
        pass

    @abstractmethod
    def task_status(self, address: str, channel: int) -> Literal["running", "ready"]:
        """check task status of the component"""
        pass

    @abstractmethod
    def task_data(self, address: str, channel: int, **kwargs) -> xr.Dataset:
        """get any cached data for the current task on the component"""
        pass

    @abstractmethod
    def task_stop(self, address: str, channel: int) -> xr.Dataset:
        """stops the current task, making the component ready and returning any data"""
        pass

    @abstractmethod
    def status(self) -> dict:
        """return status info of the driver"""
        pass

    @abstractmethod
    def teardown(self) -> None:
        """
        Stop all tasks, tear down all devices, close all processes.

        Users can assume the devices are put in a safe state (valves closed, power off).
        """
        pass
