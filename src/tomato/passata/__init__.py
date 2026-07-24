"""
.. codeauthor::
    Peter Kraus

Module of functions to interact with drivers and components of :mod:`tomato`. Includes the following functions:

- :func:`status` to query the status of a tomato component
- :func:`register` to register an individual component on a tomato driver
- :func:`attrs` to query attribute information on a component
- :func:`capabilities` to query capabilities of a component
- :func:`constants` to query constants on a component
- :func:`get_attrs` to query values of attributes on a component
- :func:`set_attr` to set value of an attribute on a component
- :func:`reset` to reset a component
- :func:`get_last_data` to retrieve the last recorded datapoint from a component
- :func:`measure` to trigger an idle measurement on a component

"""

from typing import Any

import zmq

import tomato.daemon.drvdb as drvdb
from tomato import tomato
from tomato.models import Component, DrvState, Reply
from tomato.utils import context

RCVTIMEO = 3000


def _name_to_cmp(
    name: str,
    port: int,
    timeout: int,
) -> tuple[Component, DrvState] | Reply:
    ret = tomato.status(port=port, timeout=timeout, stgrp="tomato", yaml=True)
    if ret.success is False or ret.data is None:
        return ret
    daemon = ret.data
    dbpath = daemon.settings["jobs"]["dbpath"]
    if name not in daemon.devicefile.components:
        return Reply(
            success=False,
            msg=f"component {name!r} not found on tomato",
            data=ret.data,
        )
    cmp = daemon.devicefile.components[name]
    drv = drvdb.get_drv(name=cmp.driver, dbpath=dbpath)
    assert drv is not None

    return cmp, drv


def _running_or_force(
    name: str,
    port: int,
    timeout: int,
    force: bool,
) -> Reply:
    if not force:
        ret = status(port=port, timeout=timeout, name=name)
        if not ret.success or ret.data is None:
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
    return Reply(success=True, msg="can 'set_attr'")


def status(
    *,
    port: int,
    timeout: int,
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

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
    name: str,
    attrs: list[str],
    yaml: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
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
    name: str,
    attr: str,
    val: Any,
    force: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    ret = _running_or_force(name, port, timeout, force)
    if not ret.success:
        return ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    force: bool = False,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

    ret = _running_or_force(name, port, timeout, force)
    if not ret.success:
        return ret

    kwargs = dict(channel=cmp.channel, address=cmp.address)
    req: zmq.Socket = context.socket(zmq.REQ)
    req.RCVTIMEO = RCVTIMEO
    req.connect(f"tcp://127.0.0.1:{drv.port}")
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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

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
    name: str,
    **_: dict,
) -> Reply:
    ret = _name_to_cmp(name, port, timeout)
    if isinstance(ret, Reply):
        return ret
    cmp, drv = ret
    if drv.port is None:
        return Reply(success=False, msg=f"driver {drv.name!r} has no registered port")

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
