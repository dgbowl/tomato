Usage
-----

The **tomato** package consists of two key components: 

  - the job scheduler in :mod:`tomato.daemon` executed by ``tomato``,
  - the queue management app :mod:`tomato.ketchup` executed by ``ketchup``.

The job scheduler ``tomato`` can be started in verbose mode for diagnostic output:

.. code:: bash

    tomato -vv

It is used to schedule *jobs* from the *queue* onto *pipelines*, and tracks the overall
*state* of the system. A *pipeline* is a way of organising one or many *devices* in a single, 
addressable unit, see :ref:`devfile` for more details. In general, a single *pipeline* represents
a digital twin of an experimental set-up, composed of all *devices* neccessary to carry out a 
single experimental *payload*.

.. note::

    Only one instance of the :mod:`tomato.daemon` can be running at a single PC at the
    same time, excluding any test-suite jobs (executed with the ``-t`` switch).

.. note::

    For instructions on how to set **tomato** up for a first run, see the :ref:`quickstart`.

Using :mod:`~tomato.ketchup`
````````````````````````````

The :mod:`~tomato.ketchup` executable is used to submit *payloads* to the *queue*, 
to check the status of and to cancel *jobs* in the *queue*, as well as to manage *pipelines* 
by loading or ejecting *samples* and marking *pipelines* ready for execution.

    1.  **To submit** a *job* using a *payload* contained in a :ref:`payfile` to the *queue*, run:

        .. code-block:: bash

            >>> ketchup submit <payload>
            jobid: <jobid>

        The *job* will enter the *queue* and wait for a suitable *pipeline* to begin execution.

        .. note::
    
            For more information about how *jobs* are matched against *pipelines*, see the 
            documentation of the :mod:`~tomato.daemon` module.

    2.  **To check the status** of a *job* with a known ``jobid``, run:

        .. code-block:: bash

            >>> ketchup status <jobid>
            - jobid: <jobid>
              jobname: null
              status: r
              submitted: 2022-06-30 11:18:21.538448+00:00
              executed: 2022-06-30 11:18:22.983600+00:00

        The list of possible *job* statuses is:

        ======== ===========================================================
         Status  Meaning
        ======== ===========================================================
           q     Job has entered the queue.
           qw    Job is in the queue, waiting for a pipeline to be ready.
           r     Job is running.
           c     Job has completed successfully.
           ce    Job has completed with an error.
           cd    Job has been cancelled.
        ======== ===========================================================

        .. note::

            The above command can process multiple ``jobids``, returning the information
            in a ``yaml``-formatted output.

    3.  **To cancel** a submitted *job* with a known ``jobid``, run:

        .. code-block:: bash

            >>> ketchup cancel <jobid>

.. note::

    Further information about :mod:`~tomato.ketchup` is available in the documentation
    of the :mod:`~tomato.ketchup` module.

Accessing output data
`````````````````````

Final job data
**************
By default, all data in the *job* folder is processed using ``yadg`` to create
a *datagram*, and zipped into a zip archive. This zip archive includes all raw
data files, the log file of the **tomato** job, and a copy of the full *payload* 
in a ``json`` file. The *datagram* contains timestamped, unit-annotated raw data, 
and includes instrumental uncertainties.

Unless specified within the *payload*, the default location where these output files 
will be placed is the ``cwd()`` where the ``ketchup submit`` command was executed; 
the default filenames of the returned files are ``results.<jobid>.[zip,json]``.

Data snapshotting
*****************
While the *job* is running, access to an up-to-date snapshot of the data is provided 
by :mod:`~tomato.ketchup`:

.. code:: bash

    >>> ketchup snapshot <jobid>

This will create an up-to-date ``snapshot.<jobid>.[zip,json]`` in the ``cwd()``.
The files are overwritten on subsequent invocations of ``ketchup snapshot``. An
automated, periodic snapshotting can be further configured within the *payload* 
of the *job*.