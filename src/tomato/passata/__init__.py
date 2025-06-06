import zmq
from tomato import tomato
from tomato.models import Reply, Component, Driver
from typing import Any

RCVTIMEO = 3000


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


def _running_or_force(
    name: str,
    port: int,
    timeout: int,
    context: zmq.Context,
    force: bool,
) -> Reply:
    if not force:
        ret = status(port=port, timeout=timeout, context=context, name=name)
        if not ret.success:
            return Reply(
                success=False,
                msg="will not 'set_attr' on a component with invalid status",
                data=None,
            )
        if ret.data["running"]:
            return Reply(
                success=False,
                msg=f"will not 'set_attr' on a running component {name!r}",
                data=None,
            )
    return Reply(success=True)


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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="dev_status", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="cmp_status", params={**kwargs}))
    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
    return ret


def register(
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
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="dev_register", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="cmp_register", params={**kwargs}))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="attrs", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="cmp_attrs", params={**kwargs}))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="capabilities", params={**kwargs}))
    else:
        req.send_pyobj(dict(cmd="cmp_capabilities", params={**kwargs}))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="cmp_constants", params={**kwargs}))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    data = dict()
    msg = ""
    for attr in attrs:
        if drv.version == "1.0":
            req.send_pyobj(dict(cmd="dev_get_attr", params={"attr": attr, **kwargs}))
        else:
            req.send_pyobj(dict(cmd="cmp_get_attr", params={"attr": attr, **kwargs}))
        try:
            ret = req.recv_pyobj()
        except zmq.ZMQError:
            return Reply(success=False, msg="ZMQ timeout reached")
        if ret is None or not ret.success:
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
    force: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    ret = _running_or_force(name, port, timeout, context, force)
    if not ret.success:
        return ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(
            dict(cmd="dev_set_attr", params={"attr": attr, "val": val, **kwargs})
        )
    else:
        req.send_pyobj(
            dict(cmd="cmp_set_attr", params={"attr": attr, "val": val, **kwargs})
        )

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
    return ret


def reset(
    *,
    port: int,
    timeout: int,
    context: zmq.Context,
    name: str,
    force: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout, context)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    ret = _running_or_force(name, port, timeout, context, force)
    if not ret.success:
        return ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    if drv.version == "1.0":
        req.send_pyobj(dict(cmd="dev_reset", params=kwargs))
    else:
        req.send_pyobj(dict(cmd="cmp_reset", params=kwargs))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="cmp_last_data", params=kwargs))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
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
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    if drv.version == "1.0":
        return Reply(
            success=False,
            msg=f"driver of component {name!r} is on version {drv.version}",
            data=None,
        )

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
    req.send_pyobj(dict(cmd="cmp_measure", params=kwargs))

    try:
        ret = req.recv_pyobj()
    except zmq.ZMQError:
        return Reply(success=False, msg="ZMQ timeout reached")
    req.close()
    return ret
