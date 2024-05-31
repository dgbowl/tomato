import logging
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from typing import Any
from functools import wraps

from tomato.drivers.example_counter.counter import Counter
from tomato.models import Reply, DriverInterface
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


class DriverInterface(DriverInterface):
    class DeviceInterface:
        dev: Counter
        conn: Connection
        proc: Process

        def __init__(self):
            self.dev = Counter()
            self.conn, conn = Pipe()
            self.proc = Process(target=self.dev.run_counter, args=(conn,))

    devmap: dict[tuple, DeviceInterface]
    settings: dict

    def attrs(self, **kwargs) -> dict:
        return dict(
            delay=dict(type=float, rw=True, status=False, data=True),
            time=dict(type=float, rw=True, status=False, data=True),
            started=dict(type=bool, rw=True, status=True, data=False),
            val=dict(type=int, rw=False, status=True, data=True),
        )

    def tasks(self, **kwargs) -> dict:
        return dict(
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

    def dev_register(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key] = self.DeviceInterface()
        self.devmap[key].proc.start()

    @in_devmap
    def dev_set_attr(self, attr: str, val: Any, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs():
            params = self.attrs()[attr]
            if params["rw"] and isinstance(val, params["type"]):
                self.devmap[key].conn.send(("set", attr, val))

    @in_devmap
    def dev_get_attr(self, attr: str, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs():
            self.devmap[key].conn.send(("get", attr, None))
            return self.devmap[key].conn.recv()

    @in_devmap
    def dev_status(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key].conn.send(("status", None, None))
        return self.devmap[key].conn.recv()

    @in_devmap
    def task_start(self, address: str, channel: int, task: str, **kwargs):
        if task not in self.tasks():
            return Reply(
                success=False,
                msg=f"unknown task {task!r} requested",
                data=self.tasks(),
            )

        reqs = self.tasks()[task]
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
            self.dev_set_attr(attr=k, val=val, address=address, channel=channel)
        self.dev_set_attr(attr="started", val=True, address=address, channel=channel)
        return Reply(
            success=True,
            msg=f"task {task!r} started successfully",
            data=kwargs,
        )

    @in_devmap
    def task_status(self, address: str, channel: int):
        started = self.dev_get_attr(attr="started", address=address, channel=channel)
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
        self.devmap[key].conn.send(("data", None, None))
        data = self.devmap[key].conn.recv()

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
            dev.conn.send(("stop", None, None))
            dev.proc.join(1)
            if dev.proc.is_alive():
                logger.error(f"device {key!r} is still alive")
            else:
                logger.debug(f"device {key!r} successfully closed")


if __name__ == "__main__":
    test = DriverInterface()
