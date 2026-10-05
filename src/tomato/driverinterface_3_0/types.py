from typing import TypeAlias

from pint import Quantity
from pydantic import BaseModel

Type: TypeAlias = type
Val = str | int | float | Quantity | BaseModel
