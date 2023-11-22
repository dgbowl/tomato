from pydantic import BaseModel
from typing import Union, Optional, Any


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
    devices: Optional[list[Device]] = None


class Reply(BaseModel):
    success: bool
    msg: str
    data: Optional[Any] = None
