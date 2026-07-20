"""
**tomato.models**: Pydantic models for internal tomato use
----------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any, Mapping, Sequence, Literal, Union
from typing_extensions import Self
from dgbowl_schemas.tomato import to_payload
from dgbowl_schemas.tomato.payload import Payload, Task
import logging
import pickle
import yaml

__all__ = ["Task"]
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


class Component(BaseModel):
    name: str
    driver: str
    device: str
    address: str
    channel: str
    role: str
    capabilities: Optional[set[str]] = None

    @field_validator("role", mode="after")
    def check_role(cls, value):
        if "/" in value:
            raise ValueError(
                f"Cannot have '/' as part of component.role: {value!r}, "
                "please fix your devices.yml file accordingly and run 'tomato reload'."
            )
        return value


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
    launched_at: Optional[str] = None
    connected_at: Optional[str] = None
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
        return v


class Daemon(BaseModel, arbitrary_types_allowed=True):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    appdir: str
    settings: dict = Field(default_factory=dict)
    drivers: dict[str, int] = Field(default_factory=dict)
    pips: Mapping[str, Pipeline] = Field(default_factory=dict)
    devs: Mapping[str, Device] = Field(default_factory=dict)
    drvs: Mapping[str, Driver] = Field(default_factory=dict)
    cmps: Mapping[str, Component] = Field(default_factory=dict)


class Reply(BaseModel):
    success: bool
    msg: Optional[str] = None
    data: Optional[Any] = None


class _Pipeline(BaseModel):
    name: str
    components: Mapping[str, str]


class _Component(BaseModel):
    name: str
    driver: str
    address: str
    channel: Optional[str] = None


class DeviceFile(BaseModel):
    filename: Path
    components: dict[str, _Component] = Field(default_factory=dict)
    devices: dict[str, Device] = Field(default_factory=dict)
    pipelines: dict[str, _Pipeline] = Field(default_factory=dict)

    @field_validator("filename", mode="before")
    @classmethod
    def coerce_filename(cls, val: Union[str, Path]) -> Path:
        if isinstance(val, str):
            return Path(val)
        return val

    @field_validator("filename", mode="after")
    @classmethod
    def filename_exists(cls, val: Path) -> Path:
        assert val.exists(), f"filename {val!r} does not exist"
        return val

    @model_validator(mode="after")
    def populate_attrs(self) -> Self:
        with self.filename.open("r") as inf:
            jsdata = yaml.safe_load(inf)

        devices = jsdata.get("devices", {})
        pipelines = jsdata.get("pipelines", {})

        # populate devices
        self.devices = {d["name"]: Device(**d) for d in devices}

        for pip in pipelines:
            if pip["name"].endswith("*"):
                assert len(pip["devices"]) == 1, (
                    f"only one component allowd in wildcard pipelines."
                )
                for comp in pip["devices"]:
                    assert comp["device"] in self.devices, (
                        f"device {comp['device']!r} is not specified."
                    )
                    dev = self.devices[comp["device"]]
                    assert comp["channel"] == "each", (
                        f"channel specification must be 'each', not {comp['chanel']!r}."
                    )
                    for ch in dev.channels:
                        pname = pip["name"].replace("*", ch)
                        cname = f"{dev.driver}:({dev.address},{ch})"
                        self.components[cname] = _Component(
                            name=cname,
                            driver=dev.driver,
                            address=dev.address,
                            channel=ch,
                        )
                        self.pipelines[pname] = _Pipeline(
                            name=pname,
                            components={comp["role"]: cname},
                        )
            else:
                cmps = {}
                for comp in pip["devices"]:
                    assert comp["device"] in self.devices, (
                        f"device {comp['device']!r} is not specified."
                    )
                    dev = self.devices[comp["device"]]
                    # TODO: implement optional channels here
                    assert comp["channel"] in dev.channels, (
                        f"channel {comp['channel']} is not among "
                        f"device channels {dev.channels}."
                    )
                    cname = f"{dev.driver}:({dev.address},{comp['channel']})"
                    self.components[cname] = _Component(
                        name=cname,
                        driver=dev.driver,
                        address=dev.address,
                        channel=comp["channel"],
                    )
                    cmps[comp["role"]] = cname
                self.pipelines[pip["name"]] = _Pipeline(
                    name=pip["name"],
                    components=cmps,
                )
