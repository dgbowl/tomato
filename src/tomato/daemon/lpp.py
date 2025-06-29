import zmq
from tomato.models import Reply
from typing import Any
import logging

REQ_TIMEOUT = 1000
REQ_RETRIES = 3


def comm(
    req: zmq.Socket, data: Any, endpoint: str, context: zmq.Context, retries: int = 0
) -> tuple[Reply, zmq.Socket]:
    req.send_pyobj(data)

    while True:
        if (req.poll(REQ_TIMEOUT) & zmq.POLLIN) != 0:
            ret = req.recv_pyobj()
            break

        retries += 1
        req.setsockopt(zmq.LINGER, 0)
        req.close()
        if retries >= REQ_RETRIES:
            logging.error("Server '%s' offline, abandoning", endpoint)
            ret = Reply(
                success=False,
                msg=f"Server {endpoint!r} offline, abandoning",
            )
            break
        else:
            logging.warning("Server '%s' unavailable, retry %d", endpoint, retries)
            req = context.socket(zmq.REQ)
            req.connect(endpoint)
            req.send(data)
    return ret, req
