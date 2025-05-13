from tomato.models import Reply
from tomato.driverinterface_2_1.types import Val

from functools import wraps
import logging
import sys
import pint

logger = logging.getLogger(__name__)


def in_devmap(func):
    @wraps(func)
    def wrapper(self, **kwargs):
        if "key" in kwargs:
            key = kwargs.pop("key")
        else:
            address = kwargs.get("address")
            channel = kwargs.get("channel")
            key = (address, channel)
        if key not in self.devmap:
            msg = f"dev with address {address!r} and channel {channel} is unknown"
            return Reply(success=False, msg=msg, data=self.devmap.keys())
        return func(self, **kwargs, key=key)

    return wrapper


def to_reply(func):
    """
    Helper decorator for coercing tuples into :class:`Reply`.
    """

    @wraps(func)
    def wrapper(self, **kwargs):
        ret = func(self, **kwargs)
        if isinstance(ret, Reply):
            return ret
        else:
            success, msg, data = ret
            return Reply(success=success, msg=msg, data=data)

    return wrapper


def log_errors(func):
    """
    Helper decorator for logging all kinds of errors.

    This decorator should be only used on functions in the API of the
    :class:`ModelInterface`, as the caught exceptions will cause the
    driver process to exit.
    """

    @wraps(func)
    def wrapper(self, **kwargs):
        try:
            return func(self, **kwargs)
        except Exception as e:
            logger.critical(e, exc_info=True)
            sys.exit(e)

    return wrapper


def coerce_val(func):
    """
    Decorator for coercing :obj:`val` into the correct format based on :class:`Attr` data.
    """

    @wraps(func)
    def wrapper(self, attr: str, val: Val, **kwargs: dict) -> Val:
        assert val is not None, "'val' cannot be None"
        assert attr in self.attrs(), f"unknown attr: {attr!r}"
        props = self.attrs()[attr]
        assert props.rw

        if not isinstance(val, props.type):
            val = props.type(val)
        if isinstance(val, pint.Quantity):
            if val.dimensionless and props.units is not None:
                val = pint.Quantity(val.m, props.units)
            assert val.dimensionality == pint.Quantity(props.units).dimensionality, (
                f"attr {attr!r} has the wrong dimensionality {str(val.dimensionality)}"
            )
        assert props.minimum is None or val >= props.minimum, (
            f"attr {attr!r} is smaller than {props.minimum}"
        )
        assert props.maximum is None or val <= props.maximum, (
            f"attr {attr!r} is greater than {props.maximum}"
        )

        return func(self, attr=attr, val=val, **kwargs)

    return wrapper
