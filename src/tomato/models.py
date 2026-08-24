"""
**tomato.models**: Pydantic models for internal tomato use
----------------------------------------------------------
.. codeauthor::
    Peter Kraus
"""

import logging
import pickle
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import toml
import yaml
from dgbowl_schemas.tomato import to_payload
from dgbowl_schemas.tomato.payload import Payload, Task
from pydantic import (
    BaseModel,
    Field,
    PlainSerializer,
    computed_field,
    field_validator,
    model_validator,
)

__all__ = [
    "Component",
    "Daemon",
    "Device",
    "DeviceFile",
    "Driver",
    "DrvState",
    "Job",
    "PipState",
    "Pipeline",
    "Reply",
    "Task",
]
logger = logging.getLogger(__name__)


class PipState(BaseModel):
    name: str
    ready: bool = False
    jobid: int | None = None
    sampleid: str | None = None


class DrvState(BaseModel):
    name: str
    port: int | None = None
    pid: int | None = None
    version: str | None = None
    spawn_time: float = 0.0
    spawn_count: int = 0
    heartbeat_time: float = 0.0


class Job(BaseModel):
    id: int
    payload: Payload
    jobname: str | None = None
    pid: int | None = None
    status: Literal["q", "qw", "r", "rd", "c", "cd", "ce"] = "q"
    submitted_at: str | None = None
    launched_at: str | None = None
    connected_at: str | None = None
    completed_at: str | None = None
    jobpath: str | None = None
    respath: str | None = None
    snappath: str | None = None

    @field_validator("payload", mode="before")
    @classmethod
    def coerce_payload(cls, v):
        if isinstance(v, bytes):
            v = pickle.loads(v)
        if isinstance(v, dict):
            v = to_payload(**v)
        return v


class Daemon(BaseModel, arbitrary_types_allowed=True, validate_assignment=True):
    status: Literal["bootstrap", "running", "stop"]
    port: int
    verbosity: int
    appdir: str
    settings: dict = Field(default_factory=dict)
    devicefile: "DeviceFile" = Field(default_factory="DeviceFile")

    @model_validator(mode="before")
    @classmethod
    def populate_devicefile(cls, data: Any) -> Any:
        if data.get("devicefile") is not None:
            pass
        else:
            data["devicefile"] = DeviceFile(
                filename=data["settings"]["devices"]["config"]
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def populate_settings(cls, data: Any) -> Any:
        if data.get("settings") is not None:
            pass
        else:
            data["settings"] = toml.load(Path(data.get("appdir")) / "settings.toml")
        return data

    @model_validator(mode="after")
    def device_settings(self) -> Self:
        for drv, settings in self.settings["drivers"].items():
            if drv in self.devicefile.drivers:
                self.devicefile.drivers[drv].settings.update(settings)
        return self


class Reply(BaseModel):
    success: bool
    msg: str
    data: Any | None = None


class Pipeline(BaseModel):
    name: str
    components: dict[str, str]
    """Mapping of component roles to names."""


class Component(BaseModel):
    @computed_field
    @property
    def name(self) -> str:
        """The component name, derived from the address, channel, and driver of this component."""
        if self.address is not None and self.channel is not None:
            key = f"{self.driver}:{self.address}:{self.channel}"
        elif self.address is not None:
            key = f"{self.driver}:{self.address}"
        elif self.channel is not None:
            key = f"{self.driver}::{self.channel}"
        else:
            key = f"{self.driver}"
        return key

    device: str
    driver: str
    address: str | None = None
    channel: str | None = None


class Device(BaseModel):
    name: str
    driver: str
    address: str
    channels: Sequence[str]
    pollrate: int = 1


class Driver(BaseModel):
    name: str
    settings: dict = Field(default_factory=dict)


class DeviceFile(BaseModel):
    filename: Annotated[Path, PlainSerializer(str)]
    components: dict[str, Component] = Field(default_factory=dict)
    devices: dict[str, Device] = Field(default_factory=dict)
    drivers: dict[str, Driver] = Field(default_factory=dict)
    pipelines: dict[str, Pipeline] = Field(default_factory=dict)

    @field_validator("filename", mode="before")
    @classmethod
    def coerce_filename(cls, val: str | Path) -> Path:
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

        # populate pipelines and components
        for pip in pipelines:
            if pip["name"].endswith("*"):
                assert len(pip["devices"]) == 1, (
                    "only one component allowed in wildcard pipelines."
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
                        cobj = Component(
                            device=dev.name,
                            driver=dev.driver,
                            address=dev.address,
                            channel=ch,
                        )
                        self.components[cobj.name] = cobj
                        self.pipelines[pname] = Pipeline(
                            name=pname,
                            components={comp["role"]: cobj.name},
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
                    cobj = Component(
                        device=dev.name,
                        driver=dev.driver,
                        address=dev.address,
                        channel=comp["channel"],
                    )
                    self.components[cobj.name] = cobj
                    cmps[comp["role"]] = cobj.name
                self.pipelines[pip["name"]] = Pipeline(
                    name=pip["name"],
                    components=cmps,
                )
        # populate drivers
        drivers_needed = {c.driver for c in self.components.values()}
        self.drivers = {d: Driver(name=d) for d in drivers_needed}

        return self
