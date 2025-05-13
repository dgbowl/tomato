from typing import TypeAlias, TypeVar
import pint

Type: TypeAlias = type
Val = TypeVar("Val", str, int, float, pint.Quantity)
Key: TypeAlias = tuple[str, str]
