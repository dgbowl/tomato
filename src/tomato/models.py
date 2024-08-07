"""
**tomato.models**: Pydantic models for internal tomato use
----------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Mapping, Sequence, Literal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Driver(BaseModel):
    name: str
    port: Optional[int] = None
    pid: Optional[int] = None
    spawned_at: Optional[str] = None
    connected_at: Optional[str] = None
    settings: Mapping[str, Any] = Field(default_factory=dict)


class Device(BaseModel):
    name: str
    driver: str
    address: str
    channels: Sequence[int]
    pollrate: int = 1


class Component(BaseModel):
    name: str
    driver: str
    device: str
    address: str
    channel: int
    role: str
    capabilities: Optional[set[str]] = None


class Pipeline(BaseModel):
    name: str
    ready: bool = False
    jobid: Optional[int] = None
    sampleid: Optional[str] = None
    components: Sequence[str] = Field(default_factory=list)


class Job(BaseModel):
    id: Optional[int] = None
    payload: Any
    jobname: Optional[str] = None
    pid: Optional[int] = None
    status: Literal["q", "qw", "r", "rd", "c", "cd", "ce"] = "q"
    submitted_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    jobpath: Optional[str] = None
    respath: Optional[str] = None
    snappath: Optional[str] = None


class Daemon(BaseModel, arbitrary_types_allowed=True):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    logdir: Path
    appdir: Path
    settings: dict
    pips: Mapping[str, Pipeline] = Field(default_factory=dict)
    devs: Mapping[str, Device] = Field(default_factory=dict)
    drvs: Mapping[str, Driver] = Field(default_factory=dict)
    cmps: Mapping[str, Component] = Field(default_factory=dict)
    jobs: Mapping[int, Job] = Field(default_factory=dict)
    nextjob: int = 1


class Reply(BaseModel):
    success: bool
    msg: Optional[str] = None
    data: Optional[Any] = None
