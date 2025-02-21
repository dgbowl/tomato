from abc import ABCMeta, abstractmethod
from typing import TypeVar, Any, Union, TypeAlias
from pydantic import BaseModel
from threading import Thread, current_thread, RLock
from queue import Queue
from tomato.models import Reply
from dgbowl_schemas.tomato.payload import Task
import logging
from functools import wraps
from xarray import Dataset
import time
import atexit
import pint

logger = logging.getLogger(__name__)


Type: TypeAlias = type
Val = TypeVar("Val", str, pint.Quantity)
Key: TypeAlias = tuple[str, str]


def in_devmap(func):
    @wraps(func)
    def wrapper(self, **kwargs):
        if "key" in kwargs:
            key = kwargs.pop("key")
        else:
            address = kwargs.get("address")
            channel = kwargs.get("channel")
            key = (address, channel)
        if key not in self.devmap:
            msg = f"dev with address {address!r} and channel {channel} is unknown"
            return Reply(success=False, msg=msg, data=self.devmap.keys())
        return func(self, **kwargs, key=key)

    return wrapper


def to_quantity(func):
    @wraps(func)
    def wrapper(self, **kwargs):
        if "val" in kwargs:
            v = kwargs.pop("val")
            try:
                val = pint.Quantity(v)
            except pint.errors.UndefinedUnitError:
                val = v
            kwargs["val"] = val
        return func(self, **kwargs)

    return wrapper


class Attr(BaseModel):
    """A Pydantic :class:`BaseModel` used to describe device attributes."""

    type: Type
    rw: bool = False
    status: bool = False
    units: str = None


class ModelInterface(metaclass=ABCMeta):
    """
    An abstract base class specifying the driver interface.

    Individual driver modules should expose a :class:`DriverInterface` which inherits
    from this abstract class. Only the methods of this class should be used to interact
    with drivers and their devices.
    """

    version: str = "2.0"

    devmap: dict[tuple, "ModelDevice"]
    """Map of registered devices, the tuple keys are `component = (address, channel)`"""

    settings: dict[str, Any]
    """A settings map to contain driver-specific settings such as `dllpath` for BioLogic"""

    constants: dict[str, Any]
    """A map that should be populated with driver-specific run-time constants."""

    def __init__(self, settings=None):
        self.devmap = {}
        self.constants = {}
        self.settings = settings if settings is not None else {}

    @abstractmethod
    def DeviceFactory(self, key: Key, **kwargs):
        """
        A factory function which is used to pass this instance of the :class:`ModelInterface`
        to the new :class:`ModelDevice` instance.
        """
        pass

    def dev_register(self, address: str, channel: str, **kwargs: dict) -> Reply:
        """
        Register a new device component in this driver.

        Creates a :class:`DeviceManager` representing a device component, storing it in
        the :obj:`self.devmap` using the provided `address` and `channel`.

        The returned :class:`Reply` should contain the capabilities of the registered
        component in the ``data`` slot.
        """
        key = (address, channel)
        self.devmap[key] = self.DeviceFactory(key, **kwargs)
        capabs = self.devmap[key].capabilities()
        return Reply(
            success=True,
            msg=f"device {key!r} registered",
            data=capabs,
        )

    @in_devmap
    def dev_teardown(self, key: Key, **kwargs: dict) -> Reply:
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
        self.dev_reset(key=key, **kwargs)
        del self.devmap[key]
        return Reply(
            success=True,
            msg=f"device {key!r} torn down",
        )

    @in_devmap
    def dev_reset(self, key: Key, **kwargs: dict) -> Reply:
        """
        Component reset function.

        Should set the device component into a documented, safe state. This function
        is executed at the end of every job.
        """
        self.devmap[key].reset()
        return Reply(
            success=True,
            msg=f"component {key!r} reset successfully",
        )

    @in_devmap
    def dev_set_attr(self, attr: str, val: Val, key: Key, **kwargs: dict) -> Reply:
        """
        Set value of the :class:`Attr` of the specified device component.

        Pass-through to the :func:`DeviceManager.set_attr` function. No type or
        read-write validation performed here!
        """
        self.devmap[key].set_attr(attr=attr, val=val, **kwargs)
        return Reply(
            success=True,
            msg=f"attr {attr!r} of component {key} set to {val}",
            data=val,
        )

    @in_devmap
    def dev_get_attr(self, attr: str, key: Key, **kwargs: dict) -> Reply:
        """
        Get value of the :class:`Attr` from the specified device component.

        Pass-through to the :func:`DeviceManager.get_attr` function. Units are not
        returned; those can be queried for all :class:`Attrs` using :func:`self.attrs`.

        """
        ret = self.devmap[key].get_attr(attr=attr, **kwargs)
        return Reply(
            success=True,
            msg=f"attr {attr!r} of component {key} is: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_status(self, key: Key, **kwargs: dict) -> Reply:
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
        return Reply(
            success=True,
            msg=f"component {key} is{' ' if ret['running'] else ' not '}running",
            data=ret,
        )

    @in_devmap
    def dev_capabilities(self, key: Key, **kwargs) -> Reply:
        """
        Returns the capabilities of the device component.

        Pass-through to :func:`DriverManager.capabilities`.
        """
        ret = self.devmap[key].capabilities(**kwargs)
        return Reply(
            success=True,
            msg=f"capabilities supported by component {key!r} are: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_attrs(self, key: Key, **kwargs: dict) -> Reply:
        """
        Query available :class:`Attrs` on the specified device component.

        Pass-through to the :func:`DeviceManager.attrs` function.
        """
        ret = self.devmap[key].attrs(**kwargs)
        return Reply(
            success=True,
            msg=f"attrs of component {key!r} are: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_constants(self, key: Key, **kwargs: dict) -> Reply:
        """
        Query constants on the specified device component and this driver.
        """
        ret = self.constants | self.devmap[key].constants
        return Reply(
            success=True,
            msg=f"constants of component {key!r} are: {ret}",
            data=ret,
        )

    @in_devmap
    def dev_last_data(self, key: Key, **kwargs: dict) -> Reply:
        """
        Fetch the last stored data on the component.
        """
        ret = self.devmap[key].get_last_data(**kwargs)
        if ret is None:
            return Reply(
                success=False,
                msg=f"no data present on component {key!r}",
            )
        return Reply(
            success=True,
            msg=f"last datapoint on component {key!r} at {ret.uts}",
            data=ret,
        )

    @in_devmap
    def dev_measure(self, key: Key, **kwargs: dict) -> Reply:
        """
        Do a single measurement on the component according to its current
        configuration.

        """
        if self.devmap[key].running:
            return Reply(
                success=False,
                msg=f"measurement already running on component {key!r}",
            )
        self.devmap[key].measure()
        return Reply(
            success=True,
            msg=f"measurement started on component {key!r}",
        )

    @in_devmap
    def task_start(self, key: Key, task: Task, **kwargs) -> Reply:
        """
        Submit a :class:`Task` onto the specified device component.

        Pushes the supplied :class:`Task` into the :class:`Queue` of the component,
        then starts the worker thread. Checks that the :class:`Task` is among the
        capabilities of this component.
        """
        logger.info("starting task '%s' on component %s", task.technique_name, key)
        if task.technique_name not in self.devmap[key].capabilities(**kwargs):
            return Reply(
                success=False,
                msg=f"unknown task {task.technique_name!r} requested",
                data=self.capabilities(key=key),
            )

        self.devmap[key].task_list.put(task)
        self.devmap[key].run()
        logger.info("task '%s' on component %s started", task.technique_name, key)
        return Reply(
            success=True,
            msg=f"task {task!r} started successfully",
            data=task,
        )

    @in_devmap
    def task_status(self, key: Key, **kwargs: dict) -> Reply:
        """
        Returns the task readiness status of the specified device component.

        The `running` entry in the data slot of the :class:`Reply` indicates whether
        a :class:`Task` is running. The `can_submit` entry indicates whether another
        :class:`Task` can be queued onto the device component already.
        """
        running = self.devmap[key].running
        data = dict(running=running, can_submit=not running)
        if running:
            return Reply(success=True, msg="running", data=data)
        else:
            return Reply(success=True, msg="ready", data=data)

    @in_devmap
    def task_stop(self, key: Key, **kwargs) -> Reply:
        """
        Stops a running task and returns any collected data.

        Pass-through to :func:`DriverManager.stop_task` and :func:`task_data`.
        """
        ret = self.devmap[key].stop_task(**kwargs)
        if ret is not None:
            return Reply(success=False, msg="failed to stop task", data=ret)

        ret = self.task_data(self, key=key)
        if ret.success:
            return Reply(success=True, msg=f"task stopped, {ret.msg}", data=ret.data)
        else:
            return Reply(success=True, msg=f"task stopped, {ret.msg}")

    @in_devmap
    def task_data(self, key: Key, **kwargs) -> Reply:
        """
        Return cached task data on the device component and clean the cache.

        Pass-through for :func:`DeviceManager.get_data`, with the caveat that the
        :class:`dict[list]` which is returned from the component is here converted to a
        :class:`Dataset` and annotated using units from :func:`attrs`.

        This function gets called by the job thread every `device.pollrate`, it therefore
        incurs some IPC cost.

        """
        data = self.devmap[key].get_data(**kwargs)

        if data is None:
            return Reply(success=False, msg="found no new datapoints")
        return Reply(success=True, msg=f"found {len(data)} new datapoints", data=data)

    def status(self) -> Reply:
        """
        Returns the driver status. Currently that is the names of the components in
        the `devmap`.

        """
        devkeys = self.devmap.keys()
        return Reply(
            success=True,
            msg=f"driver running with {len(devkeys)} devices",
            data=dict(devkeys=devkeys),
        )

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
            self.dev_reset(key=key)
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

    data: Union[Dataset, None]
    """Container for cached data on this component."""

    last_data: Union[Dataset, None]
    """Container for last datapoint on this component."""

    datalock: RLock
    """Lock object for thread-safe data manipulation."""

    key: Key
    """The key in :obj:`self.driver.devmap` referring to this object."""

    thread: Thread
    """The worker :class:`Thread`."""

    task_list: Queue
    """A :class:`Queue` used to pass :class:`Tasks` to the worker :class:`Thread`."""

    running: bool

    def __init__(self, driver, key, **kwargs):
        self.driver = driver
        self.key = key
        self.task_list = Queue()
        self.thread = Thread(target=self.task_runner, daemon=True)
        self.data = None
        self.last_data = None
        self.running = False
        self.datalock = RLock()
        self.constants = dict()
        atexit.register(self.reset)

    def run(self):
        """Helper function for starting the :obj:`self.thread` as a task."""
        self.thread.do_run = True
        self.thread.start()

    def measure(self):
        """Helper function for starting the :obj:`self.thread` as a measurement."""
        self.thread = Thread(target=self.meas_runner, daemon=True)
        self.thread.do_run = True
        self.thread.start()

    def task_runner(self):
        """
        Target function for the :obj:`self.thread` when handling :class:`Tasks`.

        This function waits for a :class:`Task` passed using :obj:`self.task_list`,
        then handles setting all :class:`Attrs` using the :func:`prepare_task`
        function, and finally handles the main loop of the task, periodically running
        the :func:`do_task` function (using `task.sampling_interval`) until the
        maximum task duration (i.e. `task.max_duration`) is exceeded.

        The :obj:`self.thread` is re-primed for future :class:`Tasks` at the end
        of this function.
        """
        self.running = True
        thread = current_thread()
        task: Task = self.task_list.get()
        self.prepare_task(task)
        t_start = time.perf_counter()
        t_prev = t_start
        self.data = None
        while getattr(thread, "do_run"):
            t_now = time.perf_counter()
            if t_now - t_prev > task.sampling_interval:
                with self.datalock:
                    self.do_task(task, t_start=t_start, t_now=t_now, t_prev=t_prev)
                t_prev += task.sampling_interval
            if t_now - t_start > task.max_duration:
                break
            time.sleep(max(1e-2, task.sampling_interval / 20))

        self.task_list.task_done()
        self.running = False
        self.thread = Thread(target=self.task_runner, daemon=True)
        logger.info("task '%s' on component %s is done", task.technique_name, self.key)

    def meas_runner(self):
        """
        Target function for the :obj:`self.thread` when performing one shot measurements.

        Performs the measurement using :func:`self.do_measure()`. Resets :obj:`self.thread`
        for future :class:`Tasks`.
        """
        self.running = True
        self.do_measure()
        self.running = False
        self.thread = Thread(target=self.task_runner, daemon=True)
        logger.info("measurement on component %s is done", self.key)

    def prepare_task(self, task: Task, **kwargs: dict):
        """
        Given a :class:`Task`, prepare this component for execution by setting all
        :class:`Attrs` as specified in the `task.technique_params` dictionary.
        """
        if task.technique_params is not None:
            for k, v in task.technique_params.items():
                self.set_attr(attr=k, val=v)

    @abstractmethod
    def do_task(self, task: Task, **kwargs: dict):
        """
        Periodically called task execution function.

        This function is responsible for updating :obj:`self.data` with new data, i.e.
        performing the measurement. It should also update the value of :obj:`self.last_data`,
        so that the component status is consistent with the cached data.
        """
        pass

    @abstractmethod
    def do_measure(self, **kwargs: dict) -> None:
        """
        One shot execution worker function.

        This function is performs a measurement using the current configuration of
        :obj:`self.attrs`, and stores the result in :obj:`self.last_data`.
        """
        pass

    def stop_task(self, **kwargs: dict):
        """Stops the currently running task."""
        logger.info("stopping running task on component %s", self.key)
        setattr(self.thread, "do_run", False)

    @abstractmethod
    def set_attr(self, attr: str, val: Val, **kwargs: dict) -> Val:
        """Sets the specified :class:`Attr` to `val`."""
        pass

    @abstractmethod
    def get_attr(self, attr: str, **kwargs: dict) -> Val:
        """Reads the value of the specified :class:`Attr`."""
        pass

    def get_data(self, **kwargs: dict) -> Dataset:
        """
        Returns the cached :obj:`self.data` as a :class:`xr.Dataset` before
        clearing the cache.
        """
        with self.datalock:
            ret = self.data
            self.data = None
        return ret

    def get_last_data(self, **kwargs: dict) -> Dataset:
        """Returns the :obj:`last_data` object as a :class:`xr.Dataset`."""
        return self.last_data

    @abstractmethod
    def attrs(**kwargs) -> dict[str, Attr]:
        """Returns a :class:`dict` of all available :class:`Attrs`."""
        pass

    @abstractmethod
    def capabilities(**kwargs) -> set:
        """Returns a :class:`set` of all supported techniques."""
        pass

    def status(self, **kwargs) -> dict:
        """Compiles a status report from :class:`Attrs` marked as `status=True`."""
        status = {}
        for attr, props in self.attrs().items():
            if props.status:
                status[attr] = self.get_attr(attr)
        return status

    def reset(self, **kwargs) -> None:
        """Resets the component to an initial status."""
        logger.info("resetting component %s", self.key)
        self.task_list = Queue()
        self.thread = Thread(target=self.task_runner, daemon=True)
        self.data = None
        self.running = False
        self.datalock = RLock()
