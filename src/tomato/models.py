"""
**tomato.models**: Pydantic models for internal tomato use
----------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Mapping, Sequence, Literal
from dgbowl_schemas.tomato import to_payload
from dgbowl_schemas.tomato.payload import Payload
import logging
import pickle


logger = logging.getLogger(__name__)


class Driver(BaseModel):
    name: str
    version: Optional[str] = None
    port: Optional[int] = None
    pid: Optional[int] = None
    spawned_at: Optional[str] = None
    connected_at: Optional[str] = None
    settings: Mapping[str, Any] = Field(default_factory=dict)


class Device(BaseModel):
    name: str
    driver: str
    address: str
    channels: Sequence[str]
    pollrate: int = 1

    @field_validator("channels", mode="before")
    def coerce_channels(cls, v):
        if any([isinstance(vv, int) for vv in v]):
            logger.warning(
                "Supplying 'channels' as a Sequence[int] is deprecated "
                "and will stop working in tomato-2.0."
            )
            return [str(vv) for vv in v]
        return v


class Component(BaseModel):
    name: str
    driver: str
    device: str
    address: str
    channel: str
    role: str
    capabilities: Optional[set[str]] = None

    @field_validator("channel", mode="before")
    def coerce_channel(cls, v):
        if isinstance(v, int):
            logger.warning(
                "Supplying 'channel' as an int is deprecated "
                "and will stop working in tomato-2.0."
            )
            return str(v)
        return v


class Pipeline(BaseModel):
    name: str
    ready: bool = False
    jobid: Optional[int] = None
    sampleid: Optional[str] = None
    components: Sequence[str] = Field(default_factory=list)


class Job(BaseModel):
    id: Optional[int] = None
    payload: Payload
    jobname: Optional[str] = None
    pid: Optional[int] = None
    status: Literal["q", "qw", "r", "rd", "c", "cd", "ce"] = "q"
    submitted_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    jobpath: Optional[str] = None
    respath: Optional[str] = None
    snappath: Optional[str] = None

    @field_validator("payload", mode="before")
    def coerce_payload(cls, v):
        if isinstance(v, bytes):
            v = pickle.loads(v)
        if isinstance(v, dict):
            v = to_payload(**v)
        # while hasattr(v, "update"):
        #    v = v.update()
        return v


class Daemon(BaseModel, arbitrary_types_allowed=True):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    appdir: str
    settings: dict
    pips: Mapping[str, Pipeline] = Field(default_factory=dict)
    devs: Mapping[str, Device] = Field(default_factory=dict)
    drvs: Mapping[str, Driver] = Field(default_factory=dict)
    cmps: Mapping[str, Component] = Field(default_factory=dict)


class Reply(BaseModel):
    success: bool
    msg: Optional[str] = None
    data: Optional[Any] = None
