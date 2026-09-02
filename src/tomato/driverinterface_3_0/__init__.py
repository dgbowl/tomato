"""
.. codeauthor::
    Peter Kraus
"""

import atexit
import importlib
import logging
import queue
import time
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from threading import RLock, Thread, current_thread
from typing import Any, Literal

import pint
import xarray as xr
from pydantic import BaseModel, Field

from tomato.driverinterface_3_0.decorators import in_devmap, log_errors, to_reply
from tomato.driverinterface_3_0.types import Type, Val
from tomato.models import Reply, Task

logger = logging.getLogger(__name__)


class Attr(BaseModel, arbitrary_types_allowed=True):
    """A :class:`~pydantic.BaseModel` used to describe device attributes."""

    type: Type
    """Data type of the attribute"""

    rw: bool = False
    """Is the attribute read-write?"""

    status: bool = False
    """Should the attribute be included in component status?"""

    units: str | None = None
    """Default units for the attribute, optional."""

    maximum: float | pint.Quantity | None = Field(None, union_mode="left_to_right")
    """Maximum value for the attribute, optional."""

    minimum: float | pint.Quantity | None = Field(None, union_mode="left_to_right")
    """Minimum value for the attribute, optional."""

    options: set | None = None
    """Allowed set of values for the attribute, optional."""


class Status(BaseModel):
    """A :class:`~pydantic.BaseModel` used to describe component status."""

    connected: bool
    """Indicates whether component is communicating correctly."""

    state: Literal["idle", "meas", "task", "stop"] | None
    """
    Indicates device state:

        - ``idle`` when component is connected and idle,
        - ``meas`` when component is doing an idle measurement,
        - ``task`` when component has a running task,
        - ``stop`` when component is being torn down or reset,
        - None when component is not connected.
    """

    can_submit: bool
    """Indicates whether a :class:`Task` can be sent to component queue."""

    attrs: dict[str, Any] = Field(default_factory=dict)
    """Container for any attrs that are returned as part of a status."""


class ModelInterface(metaclass=ABCMeta):
    """
    An abstract base class specifying the driver interface.

    Individual driver modules should expose a :class:`DriverInterface` as a top-level import, which inherits from this abstract class. Only the methods of this class are used to interact with *drivers* and their *components*.

    All methods of this class should return :class:`Reply` objects (except the :func:`~ModelInterface.ComponentFactory` function). However, for better readability, a decorator function :func:`to_reply` is provided, so that the types of the return values can be explicitly defined here.

    """

    # Class attributes
    version: str = "3.0"
    """Version of the :obj:`DriverInterface`."""

    idle_measurement_interval: int | None = None
    """The interval (in seconds) after which :func:`self.cmp_measure` will be executed, when idle."""

    @property
    def name(self) -> str:
        """Property that should return the name of this driver."""
        return self.__module__.replace("tomato_", "")

    # Instance attributes
    devmap: dict[str, "ModelComponent"]
    """Map of registered device components, the keys are set from the :obj:`tomato.models.Component.name`."""

    retries: dict[str, int]
    """Map of components which failed to register, with number of retries as values."""

    settings: dict[str, Any]
    """A settings map to contain driver-specific settings such as ``dllpath`` for BioLogic"""

    constants: dict[str, Any]
    """A map that should be populated with driver-specific run-time constants."""

    def __init__(self, settings: dict[str, Any] | None = None):
        self.devmap = {}
        self.constants = {}
        self.settings = settings if settings is not None else {}
        self.retries = defaultdict(int)
        atexit.register(self.quit)

    def ComponentFactory(self, name, **kwargs):
        """
        A factory function which is used to pass this instance of the :class:`ModelInterface` to the new :class:`ModelDevice` instance.
        """
        mod = importlib.import_module(self.__module__)
        return mod.Component(self, name, **kwargs)

    @log_errors
    @to_reply
    def cmp_register(
        self, name: str, address: str | None, channel: str | None, **kwargs: dict
    ) -> tuple[bool, str, str | None]:
        """
        Register a new device component in this driver.

        Creates a :class:`ModelDevice` representing a device component, storing it in the :obj:`self.devmap` using the provided `address` and `channel`.

        Returns the name of the registered component as the :obj:`Reply.data`.
        """
        try:
            self.devmap[name] = self.ComponentFactory(
                address=address, channel=channel, name=name, **kwargs
            )
            self.retries[name] = 0
            return (True, f"component {name!r} registered", name)
        except RuntimeError as e:
            self.retries[name] += 1
            return (False, f"failed to register {name!r}: {e!s}", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_stop(self, name: str, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Component stop function, passthrough to :func:`ModelComponent.stop`.

        Should set the device component into a documented, safe state.
        """
        self.devmap[name].stop(**kwargs)
        return (True, f"component {name!r} stopped", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_quit(self, name: str, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Component quit function, passthrough to :func:`ModelComponent.stop` and :func:`ModelComponent.quit`.

        Should set the device component into a documented, safe state, then release the component from tomato.

        The function is called when the driver is exiting normally.
        """
        self.devmap[name].stop(**kwargs)
        self.devmap[name].quit(**kwargs)
        del self.devmap[name]
        return (True, f"component {name!r} quit", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_reset(self, name: str, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Component reset function, passthrough to :func:`ModelComponent.stop` and :func:`ModelComponent.reset`.

        Should set the device component into a safe state and make it ready to accept new :class:`Tasks` if possible.

        The function is called on completion of each :class:`Payload`.
        """
        self.devmap[name].stop(**kwargs)
        self.devmap[name].reset(**kwargs)
        return (True, f"component {name!r} reset successfully", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_set_attr(
        self, attr: str, val: Val, name: str, **kwargs: dict
    ) -> tuple[bool, str, Val]:
        """
        Set value of the :class:`Attr` of the specified device component.

        Pass-through to the :func:`ModelDevice.set_attr` function. No type or read-write validation performed here! Returns the validated or coerced value as the :obj:`Reply.data`.
        """
        ret = self.devmap[name].set_attr(attr=attr, val=val, **kwargs)
        return (True, f"attr {attr!r} of component {name!r} set to {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_get_attr(
        self, attr: str, name: str, **kwargs: dict
    ) -> tuple[bool, str, Val]:
        """
        Get value of the :class:`Attr` from the specified device component.

        Pass-through to the :func:`ModelDevice.get_attr` function. No type coercion is done here. Returns the value as the :obj:`Reply.data`.

        """
        ret = self.devmap[name].get_attr(attr=attr, **kwargs)
        return (True, f"attr {attr!r} of component {name!r} is: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_status(self, name: str, **kwargs: dict) -> tuple[bool, str, Status]:
        """
        Get the status report from the specified device component.

        Returns a flag in :obj:`Reply.data['running']` indicating whether the component is running.

        Passthrough to :func:`ModelDevice.status`. Returns the :class:`dict` of attribute values marked as ``status=True``.
        """
        ret = self.devmap[name].status()
        msg = f"component {name!r} is{' ' if ret.connected else ' not '}connected"
        return (True, msg, ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_capabilities(self, name: str, **kwargs) -> tuple[bool, str, set]:
        """
        Returns the capabilities of the device component.

        Pass-through to :func:`ModelDevice.capabilities`. Returns the :class:`set` of capabilities in :obj:`Reply.data`.
        """
        ret = self.devmap[name].capabilities(**kwargs)
        return (True, f"capabilities supported by component {name!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_attrs(self, name: str, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Query available :class:`Attrs` on the specified device component.

        Pass-through to the :func:`ModelDevice.attrs` function. Returns the :class:`dict` of attributes as the :obj:`Reply.data`.
        """
        ret = self.devmap[name].attrs(**kwargs)
        return (True, f"attrs of component {name!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_constants(self, name: str, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Query constants on the specified device component and this driver.

        Returns the :class:`dict` of constants as the :obj:`Reply.data`.
        """
        ret = self.constants | self.devmap[name].constants
        return (True, f"constants of component {name!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_last_data(
        self, name: str, **kwargs: dict
    ) -> tuple[bool, str, None | xr.Dataset]:
        """
        Fetch the last stored data on the component.

        Passthrough to :func:`ModelDevice.get_last_data`. The data in the form of a :class:`xarray.Dataset` is returned as the :obj:`Reply.data`.
        """
        ret = self.devmap[name].get_last_data(**kwargs)
        if ret is None:
            return (False, f"no data present on component {name!r}", None)
        else:
            return (True, f"last datapoint on component {name!r} at {ret.uts}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_measure(self, name: str, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Do a single measurement on the component according to its current configuration.

        Fails if the component already has a running task / measurement.

        """
        if self.devmap[name].state != "idle":
            return (False, f"component {name!r} is not idle", None)
        elif not self.devmap[name].task_list.empty():
            return (False, f"task list component {name!r} not empty", None)
        else:
            self.devmap[name].task_list.put("measure")
            return (True, f"measurement started on component {name!r}", None)

    @log_errors
    @to_reply
    @in_devmap
    def task_start(
        self, name: str, task: Task, **kwargs
    ) -> tuple[bool, str, set | Task]:
        """
        Submit a :class:`Task` onto the specified device component.

        Pushes the supplied :class:`Task` into the :class:`~queue.Queue` of the component, then starts the worker thread (if not already started). Checks that the :class:`Task` is among the capabilities of this component.
        """
        ret = self.task_validate(name=name, task=task, **kwargs)
        if not ret.success:
            return ret

        logger.info("pushing task '%s' onto component %s", task.technique_name, name)
        self.devmap[name].task_list.put(task)
        return (True, f"task {task!r} started successfully", task)

    @log_errors
    @to_reply
    @in_devmap
    def task_status(self, name: str, **kwargs: dict) -> tuple[bool, str, dict]:
        status = self.devmap[name].status(**kwargs)
        data = {
            "running": status.state in {"task"},
            "can_submit": status.can_submit,
            "task": self.devmap[name].running_task,
        }
        if data["running"] is False:
            return (True, "component is idle", data)
        else:
            return (True, "component has a running task", data)

    @log_errors
    @to_reply
    @in_devmap
    def task_stop(self, name: str, **kwargs) -> tuple[bool, str, xr.Dataset | None]:
        """
        Stops a running task and returns any collected data.

        Pass-through to :func:`ModelComponent.stop_task` and :func:`ModelInterface.task_data`.

        If there is any cached data, it is returned as a :class:`xarray.Dataset` in the :obj:`Reply.data` and the cache is cleared.
        """
        self.devmap[name].stop_task(**kwargs)
        ret = self.task_data(name=name)
        return (True, f"task stopped, {ret.msg}", ret.data)

    @log_errors
    @to_reply
    @in_devmap
    def task_data(self, name: str, **kwargs) -> tuple[bool, str, xr.Dataset | None]:
        """
        Return cached task data on the device component and clean the cache.

        Pass-through for :func:`ModelDevice.get_data`, which should return a :class:`xarray.Dataset` that is fully annotated.

        This function gets called by the job thread every `device.pollrate`, it therefore incurs some IPC cost.
        """
        data = self.devmap[name].get_data(**kwargs)
        if data is None:
            return (False, "found no new datapoints", None)
        else:
            return (True, f"found {len(data)} new datapoints", data)

    @log_errors
    @to_reply
    @in_devmap
    def task_validate(self, name: str, task: Task, **kwargs) -> tuple[bool, str, None]:
        """
        Validate the provided :class:`Task` for submission on the component identified by :obj:`key`.
        """
        logger.info("validating task '%s' on component %s", task.technique_name, name)
        if task.technique_name not in self.devmap[name].capabilities(**kwargs):
            msg = f"unknown task {task.technique_name!r} requested"
            return (False, msg, None)
        attrs = self.devmap[name].attrs(**kwargs)
        if task.task_params is None:
            return (True, "task has no parameters to validate", None)
        for attr, val in task.task_params.items():
            if val is None:
                msg = f"val of attr {attr!r} cannot be None"
                return (False, msg, None)
            if attr not in attrs:
                msg = f"unknown attr: {attr!r}"
                return (False, msg, None)
            props = attrs[attr]
            if not props.rw:
                msg = f"attribute {attr!r} is read-only"
                return (False, msg, None)

            if not isinstance(val, props.type):
                try:
                    val = props.type(val)
                except (ValueError, pint.errors.UndefinedUnitError):
                    msg = f"could not coerce {attr!r} to type {props.type}"
                    return (False, msg, None)
            if props.options is not None and val not in props.options:
                msg = f"val {val!r} is not among allowed options {props.options}"
                return (False, msg, None)

            if isinstance(val, pint.Quantity):
                if val.dimensionless and props.units is not None:
                    val = pint.Quantity(val.m, props.units)
                if val.dimensionality != pint.Quantity(props.units).dimensionality:  # ty: ignore[no-matching-overload]
                    msg = f"val {val!r} has the wrong dimensionality"
                    return (False, msg, None)
            if props.minimum is not None and val < props.minimum:
                msg = f"val {val!r} is smaller than {props.minimum}"
                return (False, msg, None)
            if props.maximum is not None and val > props.maximum:
                msg = f"val {val!r} is greater than {props.maximum}"
                return (False, msg, None)
        return (True, "task validated successfully", None)

    @log_errors
    def status(self) -> Reply:
        """
        Returns the driver status. Currently that is the names of the components in the `devmap`.
        """
        devkeys = list(self.devmap.keys())
        return Reply(
            success=True,
            msg=f"driver running with {len(devkeys)} devices",
            data=devkeys,
        )

    def quit(self) -> Reply:
        """
        Driver quit function.

        Stops tasks and quits every registered component. Passthrough to :func:`ModelInterface.task_stop` and :func:`ModelInterface.cmp_quit`.

        Any driver-specific commands (such as releasing serial port etc.) should be performed ehre.

        Called when driver process is exiting.
        """
        logger.critical("quitting all components on this driver")
        for name in list(self.devmap.keys()):
            self.task_stop(name=name)
            self.cmp_quit(name=name)

        if len(self.devmap) == 0:
            return Reply(
                success=True,
                msg=f"all components on driver {self.name} have been reset",
                data=None,
            )
        else:
            return Reply(
                success=False,
                msg=f"{len(self.devmap)} components on driver {self.name} have not been reset",
                data=self.devmap,
            )

    @log_errors
    def reset(self) -> Reply:
        """
        Resets the driver.

        Called when the driver process is quitting. Instructs all remaining tasks to stop. Warns when devices linger. Passes through to :func:`cmp_reset`. This is not a pass-through to :func:`cmp_teardown`.
        """
        logger.info("resetting all components on this driver")
        for name in list(self.devmap.keys()):
            self.task_stop(name=name)
            self.cmp_reset(name=name)
        return Reply(
            success=True,
            msg="all components on driver have been reset",
        )


class ModelComponent(metaclass=ABCMeta):
    """
    An abstract base class specifying a manager for an individual component.

    This class should handle determining attributes and capabilities of the component, the reading/writing of those attributes, processing of tasks, and caching and returning of task data.
    """

    driver: ModelInterface
    """The parent :class:`DriverInterface` instance."""

    constants: dict[str, Any]
    """Constant metadata of this component."""

    data: xr.Dataset | None
    """Container for cached data on this component."""

    last_data: xr.Dataset | None
    """Container for last datapoint on this component."""

    datalock: RLock
    """Lock object for thread-safe data manipulation."""

    name: str
    """The name in :obj:`self.driver.devmap` referring to this object."""

    thread: Thread
    """The worker :class:`Thread`."""

    task_list: queue.Queue
    """A :class:`~queue.Queue` used to pass :class:`Tasks` to the worker :class:`Thread`."""

    state: str | None = None
    """A :class:`str` holding the component state."""

    running_task: Task | None = None

    def __init__(self, driver, name, **kwargs) -> None:
        self.driver = driver
        self.name = name
        self.task_list = queue.Queue()
        self.thread = Thread(target=self.task_runner, daemon=True)
        setattr(self.thread, "do_run", True)  # noqa: B010
        setattr(self.thread, "do_run_task", False)  # noqa: B010
        self.thread.start()
        self.data = None
        self.last_data = None
        self.state = "idle"
        self.running_task = None
        self.datalock = RLock()
        self.constants = {}

    def task_runner(self) -> None:
        """
        Target function for the :obj:`self.thread` when handling :class:`Tasks`.

        This function waits for a :class:`Task` passed using :obj:`self.task_list`, then handles setting all :class:`Attrs` using the :func:`prepare_task` function, and finally handles the main loop of the task, periodically running the :func:`do_task` function (using `task.sampling_interval`) until the maximum task duration (i.e. `task.max_duration`) is exceeded.

        The :obj:`self.thread` is reset to None.
        """
        thread = current_thread()
        while getattr(thread, "do_run"):  # noqa: B009
            try:
                task: Task | str = self.task_list.get(timeout=1)
            except queue.Empty:
                continue
            except Exception as e:
                logger.critical(e, exc_info=True)
                setattr(thread, "do_run", False)  # noqa: B010
                break

            try:
                setattr(thread, "do_run_task", False)  # noqa: B010
                if isinstance(task, Task):
                    self.state = "task"
                    self.running_task = task
                    self.prepare_task(task=task)
                    setattr(thread, "do_run_task", True)  # noqa: B010
                    t_0 = time.perf_counter()
                    t_p = t_0
                    self.data = None
                    while getattr(thread, "do_run_task") and getattr(thread, "do_run"):  # noqa: B009
                        t_n = time.perf_counter()
                        if t_n - t_p > task.sampling_interval:
                            with self.datalock:
                                self.do_task(task, t_start=t_0, t_now=t_n, t_prev=t_p)
                            t_p += task.sampling_interval
                        if t_n - t_0 > task.max_duration:
                            setattr(thread, "do_run_task", False)  # noqa: B010
                            break
                        # We want the inner task loop to run every 10 - 200 ms,
                        # so that cancelled tasks can be processed quickly
                        time.sleep(min(0.2, max(0.01, task.sampling_interval / 20)))
                    logger.info("%s: task '%s' is done", self.name, task.technique_name)
                elif task == "measure":
                    self.state = "meas"
                    self.do_measure()
                    logger.debug("%s: measurement is done", self.name)
                else:
                    self.state = "idle"
                    logger.critical("%s: unknown task received: '%s'", self.name, task)
                    setattr(thread, "do_run", False)  # noqa: B010
                    break
                self.task_list.task_done()
            except Exception as e:
                logger.critical(e, exc_info=True)
                setattr(thread, "do_run", False)  # noqa: B010
                break
            self.state = "idle"
            self.running_task = None
        self.state = "stop"
        logger.warning("%s: task runner thread is quitting", self.name)

    def prepare_task(self, task: Task, **kwargs: dict) -> None:
        """
        Given a :class:`Task`, prepare this component for execution by setting all :class:`Attrs` as specified in the `task.task_params` dictionary.
        """
        if task.task_params is not None:
            for k, v in task.task_params.items():
                self.set_attr(attr=k, val=v)

    def do_task(
        self, task: Task, t_start: float, t_now: float, t_prev: float, **kwargs: dict
    ) -> None:
        """
        Periodically called task execution function.

        This function is responsible for updating :obj:`self.data` with new data, i.e. performing the measurement. It should also update the value of :obj:`self.last_data`, so that the component status is consistent with the cached data.
        """
        self.do_measure(**kwargs)
        if self.data is None:
            self.data = self.last_data
        elif self.last_data is None:
            logger.warning("%s: last data is not set after measurement!", self.name)
        else:
            self.data = xr.concat(
                [self.data, self.last_data], dim="uts", data_vars="minimal"
            )

    @abstractmethod
    def do_measure(self, **kwargs: dict) -> None:
        """
        One shot execution worker function.

        This function is performs a measurement using the current configuration of :obj:`self.attrs`, and stores the result in :obj:`self.last_data`.
        """

    def stop_task(self, **kwargs: dict) -> None:
        """Stops the currently running task."""
        if hasattr(self.thread, "do_run_task"):
            logger.info("%s: sending stop task signal", self.name)
            setattr(self.thread, "do_run_task", False)  # noqa: B010
        else:
            logger.warning("%s: cannot send stop task signal on this cmp", self.name)

    @abstractmethod
    def set_attr(self, attr: str, val: Val, **kwargs: dict) -> Val:
        """
        Sets the specified :class:`Attr` to :obj:`val`.

        This function should handle any data type coercion and validation using e.g. :obj:`Attr.maximum` and :obj:`Attr.minimum`.

        Returns the coerced value corresponding to :obj:`val`.
        """

    @abstractmethod
    def get_attr(self, attr: str, **kwargs: dict) -> Val:
        """Reads the value of the specified :class:`Attr`."""

    def get_data(self, **kwargs: dict) -> xr.Dataset | None:
        """
        Returns the cached :obj:`self.data` as a :class:`xarray.Dataset` before clearing the cache.
        """
        with self.datalock:
            ret = self.data
            self.data = None
        return ret

    def get_last_data(self, **kwargs: dict) -> xr.Dataset | None:
        """Returns the :obj:`last_data` object as a :class:`xarray.Dataset`."""
        return self.last_data

    @abstractmethod
    def attrs(self, **kwargs) -> dict[str, Attr]:
        """Returns a :class:`dict` of all available :class:`Attrs`."""

    @abstractmethod
    def capabilities(self, **kwargs) -> set:
        """Returns a :class:`set` of all supported techniques."""

    @abstractmethod
    def status(self, **kwargs) -> Status:
        """
        Function indicating component status.

        The implementation of this function in the driver module should perform checks whether the components is still reachable (:obj:`Status.connected`) and what state is the component in (:obj:`Status.state`).

        The function should also compile a status report using :class:`Attrs` marked as ``status=True`` and return it as :obj:`Status.attrs`.
        """

    def stop(self, **kwargs) -> None:
        """
        Stops any activity on this component.

        This function should set the component to a safe state.

        By default a pass-through to :func:`ModelComponent.stop_task`.
        """
        self.stop_task(**kwargs)
        if self.thread.is_alive():
            logger.info("%s: stopping task thread", self.name)
            setattr(self.thread, "do_run", False)  # noqa: B010
            self.thread.join()

    @abstractmethod
    def quit(self, **kwargs) -> None:
        """
        Quits the component.

        This function makes the component ready to quit. When accessed via the :func:`ModelInterface.cmp_quit`, it is always called after :func:`ModelComponent.stop`, therefore all :class:`Tasks` on the device can be assumed to be stopped.
        """

    def reset(self, **kwargs) -> None:
        """
        Resets the component to an initial status.

        This function makes the component ready to accept new :class:`Task`. When accessed via the :func:`ModelInterface.cmp_reset`, it is always called after :func:`ModelComponent.stop`, therefore all :class:`Tasks` on the device can be assumed to be stopped.
        """
        logger.info("%s: resetting component", self.name)
        self.state = "stop"
        self.data = None
        self.datalock = RLock()
        self.task_list = queue.Queue()
        self.thread = Thread(target=self.task_runner, daemon=True)
        setattr(self.thread, "do_run", True)  # noqa: B010
        setattr(self.thread, "do_run_task", False)  # noqa: B010
        self.thread.start()
        logger.info("%s: reset of component is done", self.name)
        self.state = "idle"
