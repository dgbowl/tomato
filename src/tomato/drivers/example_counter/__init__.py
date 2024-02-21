import time
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from typing import Any

from tomato.drivers.example_counter.counter import Counter


class Driver:

    class Device:
        dev: Counter
        conn: Connection
        proc: Process

        def __init__(self):
            self.dev = Counter()
            self.conn, conn = Pipe()
            self.proc = Process(target=self.dev.run_counter, args=(conn,))

    devmap: dict[str, Device]
    settings: dict

    attrs: dict = dict(
        delay=dict(type=float, rw=True),
        started=dict(type=bool, rw=True),
        val=dict(type=int, rw=False),
    )

    def __init__(self, settings=None):
        self.devmap = {}
        self.settings = settings

    def register(self, address: str = "", **kwargs):
        self.devmap[address] = self.Device()
        self.devmap[address].proc.start()

    def set(self, attr: str, val: Any, address: str = "", **kwargs):
        if attr in self.attrs:
            if self.attrs[attr]["rw"] and isinstance(val, self.attrs[attr]["type"]):
                self.devmap[address].conn.send(("set", attr, val))

    def get(self, attr: str, address: str = "", **kwargs):
        if attr in self.attrs:
            self.devmap[address].conn.send(("get", attr, None))
            return self.devmap[address].conn.recv()

    def status(self, address: str = "", **kwargs):
        self.devmap[address].conn.send(("status", None, None))
        return self.devmap[address].conn.recv()

    def data(self, address: str = ""):
        self.devmap[address].conn.send(("data", None, None))
        return self.devmap[address].conn.recv()

    def teardown(self):
        for dev in self.devmap.values():
            dev.conn.send(("stop", None, None))


if __name__ == "__main__":
    dev = Driver()
    dev.register(address="")
    time.sleep(1)
    print(f"{dev.status()=}")
    print(f"{dev.attrs=}")
    print(f"{dev.get('delay')=}")
    print(f"{dev.set('delay', 0.1)=}")
    print(f"{dev.get('delay')=}")
    print(f"{dev.set('started', True)=}")
    time.sleep(2)
    print(f"{dev.status()=}")
    print(f"{dev.data()=}")
    print(f"{dev.set('started', False)=}")
    time.sleep(2)
    print(f"{dev.status()=}")
    print(f"{dev.data()=}")
    print(f"{dev.teardown()=}")
