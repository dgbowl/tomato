"""
**ketchup**: command line interface to **tomato**
-------------------------------------------------
.. codeauthor:: 
    Peter Kraus

Module of functions to interact with tomato. Includes job management functions:

- :func:`.submit` to submit a *job* to *queue*
- :func:`.status` to query the status of tomato's *pipelines*, its *queue*, or a *job*
- :func:`.cancel` to cancel a queued or kill a running *job*
- :func:`.snapshot` to create an up-to-date FAIR data archive of a running *job*
- :func:`.search` to find a ``jobid`` of a *job* from ``jobname``

Also includes *sample*/*pipeline* management functions:

- :func:`.load` to load a *sample* into a *pipeline*
- :func:`.eject` to remove any *sample* present in a *pipeline*
- :func:`.ready` to mark a *pipeline* as ready


"""
from .functions import submit, status, cancel, load, eject, ready, snapshot, search
