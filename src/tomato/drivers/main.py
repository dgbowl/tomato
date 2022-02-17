from typing import Any
import importlib

def driver_api(driver: str, command: str, **kwargs: dict) -> Any:
    m = importlib.import_module(f"tomato.drivers.{driver}")
    func = getattr(m, command)
    return func(**kwargs)


def driver_worker(settings: dict, pipeline: dict, payload: dict, ) -> None:
    for dev, dval in pipeline.items():
        driver = dval["driver"]
        address = dval["address"]
        channel = dval["channel"]
        skwargs = settings["drivers"][driver]
        print(skwargs)
        ret = driver_api(
            driver, 
            "get_status", 
            address = address, 
            channel = channel, 
            **skwargs
        )
        print(dev, ret)


