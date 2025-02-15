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
        port=port, timeout=timeout, context=context, stgrp="tomato", yaml=True
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
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="attrs", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="dev_attrs", params={**kwargs}))
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
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="capabilities", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="dev_capabilities", params={**kwargs}))
    ret = req.recv_pyobj()
    return ret


def constants(
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

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="dev_constants", params={**kwargs}))
    ret = req.recv_pyobj()
    return ret


def get_attrs(
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    attrs: list[str],
    yaml: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    data = dict()
    msg = ""
    for attr in attrs:
        req.send_pyobj(dict(cmd="dev_get_attr", params={"attr": attr, **kwargs}))
        ret = req.recv_pyobj()
        if not ret.success:
            return ret
        data[attr] = ret.data
        msg += f"attr {attr!r} of component {name!r} is: {ret.data}\n         "
    if yaml:
        msg = f"attrs {list(data.keys())} of component {name!r} retrieved"
    else:
        msg = msg.rstrip()
    return Reply(
        success=True,
        msg=msg,
        data=data,
    )


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


def reset(
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
    req.send_pyobj(dict(cmd="dev_reset", params=kwargs))
    ret = req.recv_pyobj()
    return ret


def get_last_data(
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

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="dev_last_data", params=kwargs))
    ret = req.recv_pyobj()
    return ret


def measure(
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

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req = context.socket(zmq.REQ)
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="dev_measure", params=kwargs))
    ret = req.recv_pyobj()
    return ret
