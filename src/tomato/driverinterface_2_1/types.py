from typing import TypeAlias, Union

import pint

Type: TypeAlias = type
Val = Union[str, int, float, pint.Quantity]
Key: TypeAlias = tuple[str, str]
