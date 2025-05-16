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
        # We want to preserve TypeErrors, ValueErrors and AttributeErrors for testing.
        # These should be then caught in the tomato-driver process.
        except (ValueError, AttributeError) as e:
            logger.critical(e, exc_info=True)
            raise e
        # Other kinds of errors we abort the driver process
        except Exception as e:
            logger.critical(e, exc_info=True)
            sys.exit(e)

    return wrapper


def coerce_val(func):
    """
    Decorator for coercing :obj:`val` into the correct format based on :class:`Attr` data.

    This decorator should be applied to the :func:`ModelDriver.set_attr` function, in
    order to check whether the supplied value is allowed (not ``None``, in ``options``,
    between ``minimum`` and ``maximum``) as well as coercing it to the right type and
    unit.
    """

    @wraps(func)
    def wrapper(self, attr: str, val: Val, **kwargs: dict) -> Val:
        if val is None:
            raise ValueError(f"attr {attr!r} cannot be None")
        if attr not in self.attrs():
            raise AttributeError(f"unknown attr: {attr!r}")
        props = self.attrs()[attr]
        if not props.rw:
            raise AttributeError(f"attr {attr!r} is read-only")

        if not isinstance(val, props.type):
            # This may raise ValueError
            val = props.type(val)
        if props.options is not None and val not in props.options:
            raise ValueError(f"val {val!r} is not in allowed options {props.options}")

        if isinstance(val, pint.Quantity):
            if val.dimensionless and props.units is not None:
                val = pint.Quantity(val.m, props.units)
            if val.dimensionality != pint.Quantity(props.units).dimensionality:
                raise ValueError(f"val {val!r} has the wrong dimensionality")
        if props.minimum is not None and val < props.minimum:
            raise ValueError(f"val {val!r} is smaller than {props.minimum}")
        if props.maximum is not None and val > props.maximum:
            raise ValueError(f"val {val!r} is greater than {props.maximum}")

        return func(self, attr=attr, val=val, **kwargs)

    return wrapper
