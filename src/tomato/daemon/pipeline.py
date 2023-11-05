from pydantic import BaseModel
from typing import Union, Optional

# from .device import Device


class Device(BaseModel):
    name: str
    tag: str
    driver: str
    address: Union[str, None]
    channel: Union[int, None]
    capabilities: list[str]
    pollrate: int = 1


class Pipeline(BaseModel):
    name: str
    ready: bool = False
    pid: Optional[int] = None
    jobid: Optional[int] = None
    sampleid: Optional[str] = None
    devices: list[Device]


if __name__ == "__main__":
    import yaml

    devstr = """  
    - devices:
        - address: null
          capabilities:
            - random
            - sequential
          channel: 10
          driver: dummy
          name: dummy_device
          pollrate: 1
          tag: worker
      jobid: null
      name: dummy-10
      pid: null
      ready: false
      sampleid: null
    """
    devices = yaml.safe_load(devstr)
    print(devices)
    print({p["name"]: Pipeline(**p) for p in devices})
