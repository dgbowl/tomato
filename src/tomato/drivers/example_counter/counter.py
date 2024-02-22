import time
import math


class Counter:
    delay: float
    val: int
    started: bool
    started_at: float
    time: float
    end: bool

    def __init__(self, delay: float = 0.5):
        self.val = 0
        self.delay = delay
        self.started = False
        self.started_at = None
        self.time = None
        self.end = False

    def run_counter(self, conn):
        t0 = time.perf_counter()
        data = []
        while True:
            tN = time.perf_counter()

            if self.started:
                if self.started_at is None:
                    self.started_at = tN
                    t0 = tN
                self.val = math.floor(tN - self.started_at)
                if tN - t0 > self.delay:
                    data.append(dict(uts=tN, val=self.val))
                    t0 += self.delay
                if self.time is not None and tN - self.started_at > self.time:
                    self.started = False
                    self.started_at = None

            cmd = None
            if conn.poll(1e-6):
                cmd, attr, val = conn.recv()

            if cmd == "set":
                if attr == "delay":
                    self.delay = val
                elif attr == "time":
                    self.time = val
                elif attr == "started":
                    self.started = val
                    data = []
            elif cmd == "get":
                if hasattr(self, attr):
                    conn.send(getattr(self, attr))
            elif cmd == "stop":
                break
            elif cmd == "status":
                conn.send(self.val)
            elif cmd == "data":
                conn.send(data)
                data = []
