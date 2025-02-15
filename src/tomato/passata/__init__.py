import zmq
from tomato import tomato
from tomato.models import Reply, Component, Driver
from typing import Any


def _name_to_cmp(
    name: str,
    port: int,
    timeout: int,
    context: zmq.Context,
) -> tuple[Component, Driver]:
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
    return cmp, drv 


def status(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="dev_status", params={**kwargs}))
    ret = req.recv_pyobj()
    req.close()
    return ret


def attrs(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="attrs", params={**kwargs}))
    ret = req.recv_pyobj()
    return ret


def capabilities(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="capabilities", params={**kwargs}))
    ret = req.recv_pyobj()
    return ret


def get_attr(
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    attr: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="dev_get_attr", params={"attr": attr, **kwargs}))
    ret = req.recv_pyobj()
    return ret


def set_attr(
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    attr: str,
    val: Any,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(
        dict(cmd="dev_set_attr", params={"attr": attr, "val": val, **kwargs})
    )
    ret = req.recv_pyobj()
    return ret


if __name__ == "__main__":
    import random

    kwargs = dict(port=1234, timeout=1000, context=zmq.Context())
    ret = status(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(ret.data)
    ret = status(
        name="psutil:(psutil-addr,1)",
        **kwargs,
    )
    print(ret.data)
    ret = attrs(
        name="psutil:(psutil-addr,1)",
        **kwargs,
    )
    print(ret.data)
    ret = capabilities(
        name="psutil:(psutil-addr,1)",
        **kwargs,
    )
    
    print(ret.data)
    ret = get_attr(
        name="psutil:(psutil-addr,1)",
        attr="cpu_count",
        **kwargs,
    )
    print(ret.data)
    ret = attrs(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(ret.data)
    ret = capabilities(
        name="example_counter:(example-addr,1)",
        **kwargs,
    )
    print(ret.data)
    ret = get_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        **kwargs,
    )
    print(ret.data)
    ret = set_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        val=random.random() * 10,
        **kwargs
    )
    print(ret.data)
    ret = get_attr(
        name="example_counter:(example-addr,1)",
        attr="max",
        **kwargs
    )
    print(ret.data)
