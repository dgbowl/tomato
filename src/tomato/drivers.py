"""
**tomato.drivers**: Shim interfacing with tomato driver packages
----------------------------------------------------------------
.. codeauthor::
    Peter Kraus

"""

import importlib
import logging

from tomato.driverinterface_2_0 import ModelInterface as MI_2_0
from tomato.driverinterface_2_1 import ModelInterface as MI_2_1
from tomato.driverinterface_3_0 import ModelInterface as MI_3_0

ModelInterface = MI_2_0 | MI_2_1 | MI_3_0

logger = logging.getLogger(__name__)


def driver_to_interface(drivername: str) -> None | ModelInterface:
    modname = f"tomato_{drivername.replace('-', '_')}"

    try:
        mod = importlib.import_module(modname)
    except ModuleNotFoundError as e:
        logger.critical("Error when loading 'DriverInteface': %s", e)
        return None
    else:
        if hasattr(mod, "DriverInterface"):
            return mod.DriverInterface
        else:
            return None
