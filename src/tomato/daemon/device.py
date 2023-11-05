from dataclasses import dataclass
from typing import Union


@dataclass
class Device:
    name: str
    tag: str
    driver: str
    address: Union[str, None]
    channel: Union[str, None]
    capabilities: list[str]
    pollrate: int
