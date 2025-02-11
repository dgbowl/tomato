import zmq
from tomato import tomato
from tomato.models import Reply
from typing import Any


def component(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    attr: str = None,
    val: Any = None,
    **_: dict,
) -> Reply:
    ret = tomato.status(
        port=port, timeout=timeout, context=context, stgrp="tom", yaml=True
    )
    if not ret.success:
        return ret
    if name not in ret.data.cmps:
        return Reply(
            success=False,
            msg=f"component {name!r} not found on tomato",
            data=ret.data,
        )
    cmp = ret.data.cmps[name]
    drv = ret.data.drvs[cmp.driver]
    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if attr is None:
        req.send_pyobj(dict(cmd="dev_status", params={**kwargs}))
        ret = req.recv_pyobj()
        req.close()
        return ret
    req.send_pyobj(dict(cmd="attrs", params={**kwargs}))
    ret = req.recv_pyobj()
    if attr is True:
        return ret
    if attr not in ret.data:
        return Reply(
            success=False,
            msg=f"attr {attr!r} not accessible on component {name!r}",
            data=ret.data,
        )
    if val is None:
        req.send_pyobj(dict(cmd="dev_get_attr", params={"attr": attr, **kwargs}))
        ret = req.recv_pyobj()
        return ret
    req.send_pyobj(
        dict(cmd="dev_set_attr", params={"attr": attr, "val": val, **kwargs})
    )
    ret = req.recv_pyobj()
    return ret


if __name__ == "__main__":
    import random

    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="example_counter:(example-addr,1)",
    )
    print(ret.data)
    ret = component(
        port=1234, timeout=1000, context=zmq.Context(), name="psutil:(psutil-addr,1)"
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="psutil:(psutil-addr,1)",
        attr=True,
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="psutil:(psutil-addr,1)",
        attr="cpu_count",
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="example_counter:(example-addr,1)",
        attr=True,
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="example_counter:(example-addr,1)",
        attr="max",
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="example_counter:(example-addr,1)",
        attr="max",
        val=random.random() * 10,
    )
    print(ret.data)
    ret = component(
        port=1234,
        timeout=1000,
        context=zmq.Context(),
        name="example_counter:(example-addr,1)",
        attr="max",
    )
    print(ret.data)
