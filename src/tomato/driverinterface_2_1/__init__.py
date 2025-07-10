"""
**DriverInterface-2.1**
-----------------------
.. codeauthor::
    Peter Kraus


"""

from abc import ABCMeta, abstractmethod
from typing import Any, Union, Optional
from pydantic import BaseModel, Field
from threading import Thread, current_thread, RLock
from collections import defaultdict
import queue
from tomato.models import Reply
from tomato.driverinterface_2_1.decorators import in_devmap, to_reply, log_errors
from tomato.driverinterface_2_1.types import Type, Val, Key
from dgbowl_schemas.tomato.payload import Task
import logging

import xarray as xr
import time
import atexit
import pint

logger = logging.getLogger(__name__)


class Attr(BaseModel, arbitrary_types_allowed=True):
    """A Pydantic :class:`BaseModel` used to describe device attributes."""

    type: Type
    """Data type of the attribute"""

    rw: bool = False
    """Is the attribute read-write?"""

    status: bool = False
    """Should the attribute be included in component status?"""

    units: str = None
    """Default units for the attribute, optional."""

    maximum: Optional[float | pint.Quantity] = Field(None, union_mode="left_to_right")
    """Maximum value for the attribute, optional."""

    minimum: Optional[float | pint.Quantity] = Field(None, union_mode="left_to_right")
    """Minimum value for the attribute, optional."""

    options: Optional[set] = None
    """Allowed set of values for the attribute, optional."""


class ModelInterface(metaclass=ABCMeta):
    """
    An abstract base class specifying the driver interface.

    Individual driver modules should expose a :class:`DriverInterface` as a top-level
    import, which inherits from this abstract class. Only the methods of this class
    are used to interact with *drivers* and their *components*.

    This class contains one abstract method, :func:`~ModelInterface.DeviceFactory`,
    that has to be re-implemented by the driver modules.

    All methods of this class should return :class:`Reply` objects (except the
    :func:`DeviceFactory` function). However, for better readability, a decorator function
    :func:`to_reply` is provided, so that the types of the return values can be
    explicitly defined here.

    """

    # Class attributes
    version: str = "2.1"
    """Version of the :obj:`DriverInterface`."""

    idle_measurement_interval: Union[int, None] = None
    """The interval (in seconds) after which :func:`self.cmp_measure` will be executed, when idle."""

    # Instance attributes
    devmap: dict[tuple, "ModelDevice"]
    """Map of registered device components, the tuple keys are `component = (address, channel)`"""

    retries: dict[tuple, int]
    """Map of components which failed to register, with number of retries as values."""

    settings: dict[str, Any]
    """A settings map to contain driver-specific settings such as ``dllpath`` for BioLogic"""

    constants: dict[str, Any]
    """A map that should be populated with driver-specific run-time constants."""

    def __init__(self, settings=None):
        self.devmap = {}
        self.constants = {}
        self.settings = settings if settings is not None else {}
        self.retries = defaultdict(int)

    @abstractmethod
    def DeviceFactory(self, key: Key, **kwargs) -> "ModelDevice":
        """
        A factory function which is used to pass this instance of the :class:`ModelInterface`
        to the new :class:`ModelDevice` instance.
        """
        pass

    def dev_register(self, **kwargs):
        logger.warning(
            "Use of 'dev_register' is deprecated in favour of 'cmp_register' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_register(**kwargs)

    def dev_teardown(self, **kwargs):
        logger.warning(
            "Use of 'dev_teardown' is deprecated in favour of 'cmp_teardown' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_teardown(**kwargs)

    def dev_reset(self, **kwargs):
        logger.warning(
            "Use of 'dev_reset' is deprecated in favour of 'cmp_reset' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_reset(**kwargs)

    def dev_set_attr(self, **kwargs):
        logger.warning(
            "Use of 'dev_set_attr' is deprecated in favour of 'cmp_set_attr' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_set_attr(**kwargs)

    def dev_get_attr(self, **kwargs):
        logger.warning(
            "Use of 'dev_get_attr' is deprecated in favour of 'cmp_get_attr' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_get_attr(**kwargs)

    def dev_status(self, **kwargs):
        logger.warning(
            "Use of 'dev_status' is deprecated in favour of 'cmp_status' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_status(**kwargs)

    def dev_capabilities(self, **kwargs):
        logger.warning(
            "Use of 'dev_capabilities' is deprecated in favour of 'cmp_capabilities' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_capabilities(**kwargs)

    def dev_attrs(self, **kwargs):
        logger.warning(
            "Use of 'dev_attrs' is deprecated in favour of 'cmp_attrs' "
            "and will stop working in tomato-3.0"
        )
        return self.cmp_attrs(**kwargs)

    @log_errors
    @to_reply
    def cmp_register(
        self, address: str, channel: str, **kwargs: dict
    ) -> tuple[bool, str, set]:
        """
        Register a new device component in this driver.

        Creates a :class:`ModelDevice` representing a device component, storing it in
        the :obj:`self.devmap` using the provided `address` and `channel`.

        Returns the :class:`set` of capabilities of the registered component as the
        :obj:`Reply.data`.
        """
        key = (address, channel)
        try:
            self.devmap[key] = self.DeviceFactory(key, **kwargs)
            capabs = self.devmap[key].capabilities()
            self.retries[key] = 0
            return (True, f"device {key!r} registered", capabs)
        except RuntimeError as e:
            self.retries[key] += 1
            return (False, f"failed to register {key!r}: {str(e)}", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_teardown(self, key: Key, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Emergency stop function.

        Should set the device component into a documented, safe state. The function is
        to be only called in case of critical errors, or when the component is being
        removed, not as part of normal operation (i.e. it is not intended as a clean-up
        after task completion).
        """
        status = self.task_status(key=key, **kwargs)
        if status.data:
            logger.warning("tearing down component %s with a running task!", key)
            self.task_stop(key=key, **kwargs)
        self.cmp_reset(key=key, do_run=False, **kwargs)
        del self.devmap[key]
        return (True, f"device {key!r} torn down", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_reset(
        self, key: Key, do_run: bool = True, **kwargs: dict
    ) -> tuple[bool, str, None]:
        """
        Component reset function.

        Should set the device component into a documented, safe state. This function
        is executed at the end of every job.
        """
        self.devmap[key].reset(do_run=do_run)
        return (True, f"component {key!r} reset successfully", None)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_set_attr(
        self, attr: str, val: Val, key: Key, **kwargs: dict
    ) -> tuple[bool, str, Val]:
        """
        Set value of the :class:`Attr` of the specified device component.

        Pass-through to the :func:`ModelDevice.set_attr` function. No type or
        read-write validation performed here! Returns the validated or coerced
        value as the :obj:`Reply.data`.
        """
        ret = self.devmap[key].set_attr(attr=attr, val=val, **kwargs)
        return (True, f"attr {attr!r} of component {key} set to {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_get_attr(
        self, attr: str, key: Key, **kwargs: dict
    ) -> tuple[bool, str, Val]:
        """
        Get value of the :class:`Attr` from the specified device component.

        Pass-through to the :func:`ModelDevice.get_attr` function. No type
        coercion is done here. Returns the value as the :obj:`Reply.data`.

        """
        ret = self.devmap[key].get_attr(attr=attr, **kwargs)
        return (True, f"attr {attr!r} of component {key} is: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_status(self, key: Key, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Get the status report from the specified device component.

        Iterates over all :class:`Attrs` on the component that have ``status=True`` and
        returns their values in the :obj:`Reply.data` as a :class:`dict`.
        """
        ret = {}
        for k, attr in self.devmap[key].attrs(key=key, **kwargs).items():
            if attr.status:
                ret[k] = self.devmap[key].get_attr(attr=k, **kwargs)

        ret["running"] = self.devmap[key].running
        msg = f"component {key} is{' ' if ret['running'] else ' not '}running"
        return (True, msg, ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_capabilities(self, key: Key, **kwargs) -> tuple[bool, str, set]:
        """
        Returns the capabilities of the device component.

        Pass-through to :func:`ModelDevice.capabilities`. Returns the :class:`set`
        of capabilities in :obj:`Reply.data`.
        """
        ret = self.devmap[key].capabilities(**kwargs)
        return (True, f"capabilities supported by component {key!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_attrs(self, key: Key, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Query available :class:`Attrs` on the specified device component.

        Pass-through to the :func:`ModelDevice.attrs` function. Returns the
        :class:`dict` of attributes as the :obj:`Reply.data`.
        """
        ret = self.devmap[key].attrs(**kwargs)
        return (True, f"attrs of component {key!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_constants(self, key: Key, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Query constants on the specified device component and this driver.

        Returns the :class:`dict` of constants as the :obj:`Reply.data`.
        """
        ret = self.constants | self.devmap[key].constants
        return (True, f"constants of component {key!r} are: {ret}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_last_data(
        self, key: Key, **kwargs: dict
    ) -> tuple[bool, str, Union[None, xr.Dataset]]:
        """
        Fetch the last stored data on the component.

        Passthrough to :func:`ModelDevice.get_last_data`. The data in the form of
        a :class:`xarray.Dataset` is returned as the :obj:`Reply.data`.
        """
        ret = self.devmap[key].get_last_data(**kwargs)
        if ret is None:
            return (False, f"no data present on component {key!r}", None)
        else:
            return (True, f"last datapoint on component {key!r} at {ret.uts}", ret)

    @log_errors
    @to_reply
    @in_devmap
    def cmp_measure(self, key: Key, **kwargs: dict) -> tuple[bool, str, None]:
        """
        Do a single measurement on the component according to its current
        configuration.

        Fails if the component already has a running task / measurement.

        """
        if self.devmap[key].running:
            return (False, f"measurement already running on component {key!r}", None)
        elif not self.devmap[key].task_list.empty():
            return (False, f"task list component {key!r} not empty", None)
        else:
            self.devmap[key].task_list.put("measure")
            return (True, f"measurement started on component {key!r}", None)

    @log_errors
    @to_reply
    @in_devmap
    def task_start(
        self, key: Key, task: Task, **kwargs
    ) -> tuple[bool, str, Union[set, Task]]:
        """
        Submit a :class:`Task` onto the specified device component.

        Pushes the supplied :class:`Task` into the :class:`~queue.Queue` of the component,
        then starts the worker thread (if not already started). Checks that the
        :class:`Task` is among the capabilities of this component.
        """
        ret = self.task_validate(key=key, task=task, **kwargs)
        if not ret.success:
            return ret

        logger.info("pushing task '%s' onto component %s", task.technique_name, key)
        self.devmap[key].task_list.put(task)
        return (True, f"task {task!r} started successfully", task)

    @log_errors
    @to_reply
    @in_devmap
    def task_status(self, key: Key, **kwargs: dict) -> tuple[bool, str, dict]:
        """
        Returns the task readiness status of the specified device component.

        The `running` entry in the data slot of the :class:`Reply` indicates whether
        a :class:`Task` is running. The `can_submit` entry indicates whether another
        :class:`Task` can be queued onto the device component already.
        """
        running = self.devmap[key].running
        can_submit = not self.devmap[key].task_list.full()
        data = dict(running=bool(running), can_submit=can_submit, task=running)
        if running is False:
            return (True, "component is idle", data)
        else:
            return (True, "component has a running task", data)

    @log_errors
    @to_reply
    @in_devmap
    def task_stop(
        self, key: Key, **kwargs
    ) -> tuple[bool, str, Union[xr.Dataset, None]]:
        """
        Stops a running task and returns any collected data.

        Pass-through to :func:`ModelDevice.stop_task` and :func:`ModelInterface.task_data`.

        If there is any cached data, it is returned as a :class:`xarray.Dataset` in the
        :obj:`Reply.data` and the cache is cleared.
        """
        self.devmap[key].stop_task(**kwargs)
        ret = self.task_data(key=key)
        return (True, f"task stopped, {ret.msg}", ret.data)

    @log_errors
    @to_reply
    @in_devmap
    def task_data(
        self, key: Key, **kwargs
    ) -> tuple[bool, str, Union[xr.Dataset, None]]:
        """
        Return cached task data on the device component and clean the cache.

        Pass-through for :func:`ModelDevice.get_data`, which should return a
        :class:`xarray.Dataset` that is fully annotated.

        This function gets called by the job thread every `device.pollrate`, it therefore
        incurs some IPC cost.

        """
        data = self.devmap[key].get_data(**kwargs)
        if data is None:
            return (False, "found no new datapoints", None)
        else:
            return (True, f"found {len(data)} new datapoints", data)

    @log_errors
    @to_reply
    @in_devmap
    def task_validate(self, key: Key, task: Task, **kwargs) -> tuple[bool, str, None]:
        """
        Validate the provided :class:`Task` for submission on the component
        identified by :obj:`key`.

        """
        logger.info("validating task '%s' on component %s", task.technique_name, key)
        if task.technique_name not in self.devmap[key].capabilities(**kwargs):
            msg = f"unknown task {task.technique_name!r} requested"
            return (False, msg, None)
        attrs = self.devmap[key].attrs(**kwargs)
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
                if val.dimensionality != pint.Quantity(props.units).dimensionality:
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
        Returns the driver status. Currently that is the names of the components in
        the `devmap`.

        """
        devkeys = list(self.devmap.keys())
        return Reply(
            success=True,
            msg=f"driver running with {len(devkeys)} devices",
            data=devkeys,
        )

    @log_errors
    def reset(self) -> Reply:
        """
        Resets the driver.

        Called when the driver process is quitting. Instructs all remaining tasks to
        stop. Warns when devices linger. Passes through to :func:`dev_reset`. This is
        not a pass-through to :func:`dev_teardown`.

        """
        logger.info("resetting all components on this driver")
        for key, dev in self.devmap.items():
            if dev.thread.is_alive():
                logger.warning("stopping task on component %s", key)
                setattr(dev.thread, "do_run", False)
                dev.thread.join(timeout=1)
            if dev.thread.is_alive():
                logger.error("task on component %s is still running", key)
            else:
                logger.debug("component %s has no running task", key)
            self.cmp_reset(key=key)
        return Reply(
            success=True,
            msg="all components on driver have been reset",
        )


class ModelDevice(metaclass=ABCMeta):
    """
    An abstract base class specifying a manager for an individual component.

    This class should handle determining attributes and capabilities of the component,
    the reading/writing of those attributes, processing of tasks, and caching and
    returning of task data.
    """

    driver: ModelInterface
    """The parent :class:`DriverInterface` instance."""

    constants: dict[str, Any]
    """Constant metadata of this component."""

    data: Union[xr.Dataset, None]
    """Container for cached data on this component."""

    last_data: Union[xr.Dataset, None]
    """Container for last datapoint on this component."""

    datalock: RLock
    """Lock object for thread-safe data manipulation."""

    key: Key
    """The key in :obj:`self.driver.devmap` referring to this object."""

    thread: Thread
    """The worker :class:`Thread`."""

    task_list: queue.Queue
    """A :class:`~queue.Queue` used to pass :class:`Tasks` to the worker :class:`Thread`."""

    running: bool

    def __init__(self, driver, key, **kwargs) -> None:
        self.driver = driver
        self.key = key
        self.task_list = queue.Queue()
        self.thread = Thread(target=self.task_runner, daemon=False)
        self.thread.do_run = True
        self.thread.do_run_task = False
        self.thread.start()
        self.data = None
        self.last_data = None
        self.running = False
        self.datalock = RLock()
        self.constants = dict()
        atexit.register(self.reset)

    def task_runner(self) -> None:
        """
        Target function for the :obj:`self.thread` when handling :class:`Tasks`.

        This function waits for a :class:`Task` passed using :obj:`self.task_list`,
        then handles setting all :class:`Attrs` using the :func:`prepare_task`
        function, and finally handles the main loop of the task, periodically running
        the :func:`do_task` function (using `task.sampling_interval`) until the
        maximum task duration (i.e. `task.max_duration`) is exceeded.

        The :obj:`self.thread` is reset to None.
        """
        thread = current_thread()
        while thread.do_run:
            try:
                task: Task = self.task_list.get(timeout=1)
            except queue.Empty:
                continue
            except Exception as e:
                logger.critical(e, exc_info=True)
                thread.do_run = False
                break

            self.running = task
            try:
                if isinstance(task, Task):
                    thread.do_run_task = True
                    self.prepare_task(task=task)
                    t_0 = time.perf_counter()
                    t_p = t_0
                    self.data = None
                    while thread.do_run_task and thread.do_run:
                        t_n = time.perf_counter()
                        if t_n - t_p > task.sampling_interval:
                            with self.datalock:
                                self.do_task(task, t_start=t_0, t_now=t_n, t_prev=t_p)
                            t_p += task.sampling_interval
                        if t_n - t_0 > task.max_duration:
                            thread.do_run_task = False
                            break
                        # We want the inner task loop to run every 10 - 200 ms,
                        # so that cancelled tasks can be processed quickly
                        time.sleep(min(0.2, max(0.01, task.sampling_interval / 20)))
                    logger.info(
                        "task '%s' on component %s is done",
                        task.technique_name,
                        self.key,
                    )
                elif task == "measure":
                    self.do_measure()
                    logger.debug("measurement on component %s is done", self.key)
                else:
                    logger.critical("Unknown task received: '%s'", task)
                    thread.do_run = False
                    break
                self.task_list.task_done()
            except Exception as e:
                logger.critical(e, exc_info=True)
                thread.do_run = False
                break
            self.running = False
        logger.warning("task runner is quitting")
        self.running = False

    def prepare_task(self, task: Task, **kwargs: dict) -> None:
        """
        Given a :class:`Task`, prepare this component for execution by setting all
        :class:`Attrs` as specified in the `task.task_params` dictionary.
        """
        if task.task_params is not None:
            for k, v in task.task_params.items():
                self.set_attr(attr=k, val=v)

    def do_task(self, task: Task, **kwargs: dict) -> None:
        """
        Periodically called task execution function.

        This function is responsible for updating :obj:`self.data` with new data, i.e.
        performing the measurement. It should also update the value of :obj:`self.last_data`,
        so that the component status is consistent with the cached data.
        """
        self.do_measure(**kwargs)
        if self.data is None:
            self.data = self.last_data
        else:
            self.data = xr.concat(
                [self.data, self.last_data], dim="uts", data_vars="minimal"
            )

    @abstractmethod
    def do_measure(self, **kwargs: dict) -> None:
        """
        One shot execution worker function.

        This function is performs a measurement using the current configuration of
        :obj:`self.attrs`, and stores the result in :obj:`self.last_data`.
        """
        pass

    def stop_task(self, **kwargs: dict) -> None:
        """Stops the currently running task."""
        logger.info("stopping running task on component %s", self.key)
        if hasattr(self.thread, "do_run_task"):
            self.thread.do_run_task = False
        else:
            logger.warning("attempted to stop a task without 'thread.do_run_task'")

    @abstractmethod
    def set_attr(self, attr: str, val: Val, **kwargs: dict) -> Val:
        """
        Sets the specified :class:`Attr` to :obj:`val`.

        This function should handle any data type coercion and validation
        using e.g. :obj:`Attr.maximum` and :obj:`Attr.minimum`.

        Returns the coerced value corresponding to :obj:`val`.
        """
        pass

    @abstractmethod
    def get_attr(self, attr: str, **kwargs: dict) -> Val:
        """Reads the value of the specified :class:`Attr`."""
        pass

    def get_data(self, **kwargs: dict) -> xr.Dataset:
        """
        Returns the cached :obj:`self.data` as a :class:`xarray.Dataset` before
        clearing the cache.
        """
        with self.datalock:
            ret = self.data
            self.data = None
        return ret

    def get_last_data(self, **kwargs: dict) -> xr.Dataset:
        """Returns the :obj:`last_data` object as a :class:`xarray.Dataset`."""
        return self.last_data

    @abstractmethod
    def attrs(**kwargs) -> dict[str, Attr]:
        """Returns a :class:`dict` of all available :class:`Attrs`."""
        pass

    @abstractmethod
    def capabilities(**kwargs) -> set:
        """Returns a :class:`set` of all supported techniques."""
        pass

    def status(self, **kwargs) -> dict[str, Val]:
        """Compiles a status report from :class:`Attrs` marked as `status=True`."""
        status = {}
        for attr, props in self.attrs().items():
            if props.status:
                status[attr] = self.get_attr(attr)
        return status

    def reset(self, do_run: bool = True, **kwargs) -> None:
        """
        Resets the component to an initial status.

        Stops any running :class:`Tasks` or measurements. Clears the
        :obj:`task_list` queue. Resets :obj:`data` and creates a new
        :obj:`datalock`. Restarts the task processing :class:`Thread`.

        """
        logger.info("resetting component %s", self.key)
        if hasattr(self.thread, "do_run"):
            self.thread.do_run = False
        logger.info("component %s is waiting for task thread", self.key)
        self.thread.join()
        logger.info("component %s is continuing with reset", self.key)
        self.running = False
        self.data = None
        self.datalock = RLock()
        self.task_list = queue.Queue()
        self.thread = Thread(target=self.task_runner, daemon=False)
        self.thread.do_run = do_run
        self.thread.do_run_task = False
        self.thread.start()
        logger.info("reset of component %s done", self.key)
