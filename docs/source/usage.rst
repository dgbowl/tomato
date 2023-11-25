Usage
-----

The **tomato** package consists of two user-facing utilities: 

  - the daemon management utility, :mod:`tomato.tomato`, executed by ``tomato``,
  - the queue management app, :mod:`tomato.ketchup`, executed by ``ketchup``.

Starting :mod:`tomato.daemon`
``````````````````````````````

Provided a *settings file* exists, the job scheduler ``tomato`` can be started on the 
default *port* using:

.. code:: bash

    tomato start

The daemon keeps track of *pipelines* configured in the *device file*, and schedules 
*jobs* from the *queue* onto them. A *pipeline* is a way of organising one or many 
*devices* in a single, addressable unit, see :ref:`devfile` for more details. In 
general, a single *pipeline* represents a digital twin of an experimental set-up, 
composed of all *devices* neccessary to carry out a single experimental *payload*.

.. note::

    Multiple instances of the :mod:`tomato.daemon` can be running at a single PC, 
    provided a different *port* is specified using ``--port`` argument to ``tomato``
    and ``ketchup``.

.. note::

    For instructions on how to set **tomato** up for a first run, see the 
    :ref:`quickstart`.

Using :mod:`~tomato.tomato`
```````````````````````````
The :mod:`tomato.tomato` executable is used to configure, start, and manage the 
**tomato** daemon, as well as load / eject samples to / from *pipelines* and mark them
ready.

    #. **To configure** the **tomato** daemon by creating a default *settings file*, 
    run:

        .. code-block:: bash

            >>> tomato init

    #. **To start** the **tomato** daemon on the default port, run:

        .. code-block:: bash

            >>> tomato start
    
        This will read the *settings file*, and parse the *device file* listed within.
        To start the **daemon on an alternative port**, run:

        .. code-block:: bash

            >>> tomato start --port <int>

        .. note::

            All ``tomato`` and ``ketchup`` commands intended to interact with the 
            **tomato** daemon running on an alternative port will have to be executed
            with the same ``--port <int>`` argument.
        
    #. **To stop** the **tomato** daemon, run:

        .. code-block:: bash

            >>> tomato stop
    
    #. **To reload settings** of a running **tomato** daemon, run:

        .. code-block:: bash

            >>> tomato reload

    #. **To manage individual pipelines** of a running **tomato** daemon, the following
        commands are available:

        - For loading a sample into a *pipeline*:

            .. code-block:: bash

                >>> tomato pipeline load <sampleid> <pipeline>
        
            This will only succeed on *pipelines* that are empty and have no jobs running.
        
        - To eject any sample from a *pipeline*:

            .. code-block:: bash

                >>> tomato pipeline eject <pipeline>
        
            This will also succeed if the *pipeline* was already empty. It will fail
            if the *pipeline* has a job running.

            .. note::

                Ejecting a sample from any *pipeline* will mark the *pipeline* as not ready.

        - To mark a *pipeline* as ready:

            .. code-block:: bash

                >>> tomato pipeline ready <pipeline>
            
            This will also succeed if the *pipeline* was already ready. 


Using :mod:`~tomato.ketchup`
````````````````````````````

The :mod:`tomato.ketchup` executable is used to submit *payloads* to the *queue*, and
to check the status of and to cancel *jobs* in the *queue*.

    #.  **To submit** a *job* using a *payload* contained in a :ref:`payfile` to the *queue*, run:

        .. code-block:: bash

            >>> ketchup submit <payload>
            jobid: <jobid>

        The *job* will enter the *queue* and wait for a suitable *pipeline* to begin execution.

        .. note::
    
            For more information about how *jobs* are matched against *pipelines*, see the 
            documentation of the :mod:`~tomato.daemon` module.

    #.  **To check the status** of a *job* with a known ``jobid``, run:

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
           rd    Job has been marked for cancellation.
           c     Job has completed successfully.
           ce    Job has completed with an error.
           cd    Job has been cancelled.
        ======== ===========================================================

        .. note::

            The above command can process multiple ``jobids``, returning the information
            in a ``yaml``-formatted output.

    #.  **To cancel** a submitted *job* with a known ``jobid``, run:

        .. code-block:: bash

            >>> ketchup cancel <jobid>

        This will mark the `job` for cancellation by setting its status to ``rd``. The
        :mod:`tomato.daemon` will then proceed with cancelling the `job`.

*Jobs* submitted to the *queue* will remain in the *queue* until a *pipeline* meets all
of the following criteria:

  - A *pipeline* which matches all of the ``techniques`` specified in the *payload* 
    by its ``capabilities`` must exist. Once the :mod:`tomato.daemon` finds such a 
    *pipeline*, the status of the *job* will change to ``qw``.
  - The matching *pipeline* must contain a *sample* with a ``samplename`` that matches 
    the name specified in the *payload*.
  - The matching *pipeline* must be marked as ``ready``.

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