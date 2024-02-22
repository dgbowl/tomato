import time
import logging
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from typing import Any
from functools import wraps

from tomato.drivers.example_counter.counter import Counter
from tomato.models import Reply
from xarray import Dataset, DataArray

logger = logging.getLogger(__name__)


class Driver:

    class Device:
        dev: Counter
        conn: Connection
        proc: Process

        def __init__(self):
            self.dev = Counter()
            self.conn, conn = Pipe()
            self.proc = Process(target=self.dev.run_counter, args=(conn,))

    devmap: dict[tuple, Device]
    settings: dict

    attrs: dict = dict(
        delay=dict(type=float, rw=True),
        time=dict(type=float, rw=True),
        started=dict(type=bool, rw=True),
        val=dict(type=int, rw=False),
    )

    tasks: dict = dict(
        count=dict(
            time=dict(type=float),
            delay=dict(type=float),
        ),
        random=dict(
            time=dict(type=float),
            delay=dict(type=float),
            min=dict(type=float),
            max=dict(type=float),
        ),
    )

    def __init__(self, settings=None):
        self.devmap = {}
        self.settings = settings if settings is not None else {}

    def in_devmap(func):

        @wraps(func)
        def wrapper(self, **kwargs):
            address = kwargs.get("address")
            channel = kwargs.get("channel")
            if (address, channel) not in self.devmap:
                return Reply(
                    success=False,
                    msg=f"device with address {address!r} and channel {channel} is unknown",
                    data=self.devmap.keys(),
                )
            return func(self, **kwargs)

        return wrapper

    def dev_register(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key] = self.Device()
        self.devmap[key].proc.start()

    @in_devmap
    def dev_attr_set(self, attr: str, val: Any, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs:
            if self.attrs[attr]["rw"] and isinstance(val, self.attrs[attr]["type"]):
                self.devmap[key].conn.send(("set", attr, val))

    @in_devmap
    def dev_attr_get(self, attr: str, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs:
            self.devmap[key].conn.send(("get", attr, None))
            return self.devmap[key].conn.recv()

    @in_devmap
    def dev_status(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key].conn.send(("status", None, None))
        return self.devmap[key].conn.recv()

    @in_devmap
    def task_status(self, address: str, channel: int):
        started = self.dev_attr_get(attr="started", address=address, channel=channel)
        if not started:
            return Reply(success=True, msg="ready")
        else:
            return Reply(success=True, msg="running")

    @in_devmap
    def task_start(self, address: str, channel: int, task: str, **kwargs):
        if task not in self.tasks:
            return Reply(
                success=False,
                msg=f"unknown task {task!r} requested",
                data=self.tasks,
            )

        reqs = self.tasks[task]
        for k, v in reqs.items():
            if k not in kwargs and "default" not in v:
                logger.critical("Somehow we're here")
                logger.critical(f"{k=} {kwargs=}")
                logger.critical(f"{v=}")
                return Reply(
                    success=False,
                    msg=f"required parameter {k!r} missing",
                    data=reqs,
                )
            val = kwargs.get(k, v.get("default"))
            logger.critical(f"{k=} {val=}")
            if not isinstance(val, v["type"]):
                return Reply(
                    success=False,
                    msg=f"parameter {k!r} is wrong type",
                    data=reqs,
                )
            self.dev_attr_set(attr=k, val=val, address=address, channel=channel)
        self.dev_attr_set(attr="started", val=True, address=address, channel=channel)
        return Reply(
            success=True,
            msg=f"task {task!r} started successfully",
            data=kwargs,
        )

    @in_devmap
    def task_data(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key].conn.send(("data", None, None))
        data = self.devmap[key].conn.recv()
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

        return Reply(
            success=True,
            msg=f"found {len(data)} new datapoints",
            data=ds,
        )

    def status(self):
        devkeys = self.devmap.keys()
        return Reply(
            success=True,
            msg=f"driver running with {len(devkeys)} devices",
            data=dict(devkeys=devkeys),
        )

    def teardown(self):
        for key, dev in self.devmap.items():
            dev.conn.send(("stop", None, None))
            dev.proc.join(1)
            if dev.proc.is_alive():
                logger.error(f"device {key!r} is still alive")
            else:
                logger.debug(f"device {key!r} successfully closed")
