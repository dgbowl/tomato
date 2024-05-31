"""
Driver documentation goes here.
"""
import importlib
import logging

from typing import Union
from tomato.models import ModelInterface

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