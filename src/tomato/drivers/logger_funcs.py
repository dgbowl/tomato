import logging
import logging.handlers


def log_listener_config(path: str):
    root = logging.getLogger()
    h = logging.FileHandler(path, mode="a")
    f = logging.Formatter("%(asctime)s:%(levelname)-8s:%(processName)-10s:%(message)s")
    h.setFormatter(f)
    root.addHandler(h)


def log_listener(queue, configurer, path):
    configurer(path)
    while True:
        record = queue.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)


def log_worker_config(queue, loglevel=logging.INFO):
    h = logging.handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(loglevel)
