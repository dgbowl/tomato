"""
**tomato.drivers**: Shim interfacing with tomato driver packages
----------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import importlib
import logging

from typing import Union, TypeVar
from tomato.driverinterface_1_0 import ModelInterface as MI_1_0
from tomato.driverinterface_2_0 import ModelInterface as MI_2_0
from tomato.driverinterface_2_1 import ModelInterface as MI_2_1

ModelInterface = TypeVar("ModelInterface", MI_1_0, MI_2_0, MI_2_1)

logger = logging.getLogger(__name__)


def driver_to_interface(drivername: str) -> Union[None, ModelInterface]:
    modname = f"tomato_{drivername.replace('-', '_')}"

    try:
        mod = importlib.import_module(modname)
    except ModuleNotFoundError as e:
        logger.critical("Error when loading 'DriverInteface': %s", e)
        return None
    else:
        if hasattr(mod, "DriverInterface"):
            return getattr(mod, "DriverInterface")
        else:
            return None
