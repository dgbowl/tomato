from pydantic import BaseModel, Field
from typing import Union, Optional, Any, Mapping, Literal


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


class Job(BaseModel):
    jobid: int
    jobname: Optional[str] = None
    pid: Optional[int] = None
    status: Literal["q", "qw", ""] = "q"


class Reply(BaseModel):
    success: bool
    msg: str
    data: Optional[Any] = None


class Daemon(BaseModel):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    logdir: str
    pipelines: Mapping[str, Pipeline] = Field(default_factory=dict)
    devices: Mapping[str, Device] = Field(default_factory=dict)
    jobs: Mapping[int, Job] = Field(default_factory=dict)
