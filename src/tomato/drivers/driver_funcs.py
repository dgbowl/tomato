from typing import Any
import importlib
import time

def driver_api(driver: str, command: str, **kwargs: dict) -> Any:
    m = importlib.import_module(f"tomato.drivers.{driver}")
    func = getattr(m, command)
    return func(**kwargs)


def driver_worker(settings: dict, pipeline: dict, payload: dict, ) -> None:
    for dev, dval in pipeline.items():
        driver = dval["driver"]
        address = dval["address"]
        channel = dval["channel"]
        driver_args = settings["drivers"][driver]
        ts, data = driver_api(
            driver, 
            "get_status", 
            address = address, 
            channel = channel, 
            **driver_args
        )
        print(ts, data["channel_state"])

    for dev, dval in pipeline.items():
        driver = dval["driver"]
        address = dval["address"]
        channel = dval["channel"]
        ts = driver_api(
            driver,
            "start_job",
            address = address,
            channel = channel,
            payload = payload["method"][dev],
            **driver_args,
            **payload["sample"]
        )
        ts, data = driver_api(
            driver, 
            "get_status", 
            address = address, 
            channel = channel, 
            **driver_args
        )
        print(ts, data["channel_state"])
    
    retdata = []
    cont = True
    while cont:
        for dev, dval in pipeline.items():
            driver = dval["driver"]
            address = dval["address"]
            channel = dval["channel"]
            ts, data = driver_api(
                driver,
                "get_data",
                address = address,
                channel = channel,
                **driver_args
            )
            retdata.append(data)
            ts, data = driver_api(
                driver, 
                "get_status", 
                address = address, 
                channel = channel, 
                **driver_args
            )
            print(ts, data["channel_state"])
            if data["channel_state"] == "STOP":
                cont = False
        time.sleep(1)
    print(retdata)
        


