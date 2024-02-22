import time
import logging
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from typing import Any

from tomato.drivers.example_counter.counter import Counter

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
        started=dict(type=bool, rw=True),
        val=dict(type=int, rw=False),
    )

    def __init__(self, settings=None):
        self.devmap = {}
        self.settings = settings if settings is not None else {}

    def register(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key] = self.Device()
        self.devmap[key].proc.start()

    def set(self, attr: str, val: Any, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs:
            if self.attrs[attr]["rw"] and isinstance(val, self.attrs[attr]["type"]):
                self.devmap[key].conn.send(("set", attr, val))

    def get(self, attr: str, address: str, channel: int, **kwargs):
        key = (address, channel)
        if attr in self.attrs:
            self.devmap[key].conn.send(("get", attr, None))
            return self.devmap[key].conn.recv()

    def status(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key].conn.send(("status", None, None))
        return self.devmap[key].conn.recv()

    def data(self, address: str, channel: int, **kwargs):
        key = (address, channel)
        self.devmap[key].conn.send(("data", None, None))
        return self.devmap[key].conn.recv()

    def teardown(self, **kwargs):
        for key, dev in self.devmap.items():
            dev.conn.send(("stop", None, None))
            dev.proc.join(1)
            if dev.proc.is_alive():
                logger.error(f"device {key!r} is still alive")
            else:
                logger.debug(f"device {key!r} successfully closed")
