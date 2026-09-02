from typing import TypeAlias

import pint

Type: TypeAlias = type
Val = str | int | float | pint.Quantity
Key: TypeAlias = tuple[str, str]
