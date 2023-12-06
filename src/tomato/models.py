from pydantic import BaseModel, Field
from typing import Union, Optional, Any, Mapping, Literal
from pathlib import Path
import toml


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
    jobid: Optional[int] = None
    sampleid: Optional[str] = None
    devices: Optional[list[Device]] = None


class Job(BaseModel):
    id: int
    payload: Any
    jobname: Optional[str] = None
    pid: Optional[int] = None
    status: Literal["q", "qw", "r", "rd", "c", "cd", "ce"] = "q"
    submitted_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None


class Daemon(BaseModel, arbitrary_types_allowed=True):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    logdir: Path
    appdir: Path
    settings: dict
    pips: Mapping[str, Pipeline] = Field(default_factory=dict)
    devs: Mapping[str, Device] = Field(default_factory=dict)
    jobs: Mapping[int, Job] = Field(default_factory=dict)
    nextjob: int = 1


class Reply(BaseModel):
    success: bool
    msg: str
    data: Optional[Any] = None
