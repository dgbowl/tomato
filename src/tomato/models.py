from pydantic import BaseModel, Field
from typing import Union, Optional, Any, Mapping, Sequence, Literal
from pathlib import Path


class Device(BaseModel):
    name: str
    driver: str
    address: Union[str, None]
    channels: Optional[Sequence[int]] = None
    capabilities: Sequence[str]
    pollrate: int = 1
    settings: Mapping[str, Any] = Field(default_factory=dict)


class Pipeline(BaseModel):
    class Component(BaseModel):
        channel: int
        role: str

    name: str
    ready: bool = False
    jobid: Optional[int] = None
    sampleid: Optional[str] = None
    devs: Mapping[str, Component] = Field(default_factory=dict)


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
