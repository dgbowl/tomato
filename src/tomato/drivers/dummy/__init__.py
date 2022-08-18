"""
This is a driver for debugging purposes.

Supported *method* parameters:
---------------------------------
============== ========================================= ===========================================
Parameter      Type                                      Meaning
============== ========================================= ===========================================
``technique``  :class:`Literal["random", "sequential"]`  see below
``time``       :class:`Union[int,float]`                 total runtime of the *method*
``delay``      :class:`Union[int,float]`                 delay between datapoints
============== ========================================= ===========================================

Supported ``techniques``:
`````````````````````````
- ``random``: returns a random :class:`float` value
- ``sequential``: returns a sequentially increasing :class:`int` value


.. codeauthor::
    Peter Kraus

"""
from .main import get_status, get_data, start_job, stop_job
