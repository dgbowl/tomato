Usage
-----

The **tomato** package consists of two user-facing utilities:

  - the state daemon management utility, :mod:`tomato.tomato`, executed by ``tomato``,
  - the job and queue management app, :mod:`tomato.ketchup`, executed by ``ketchup``.

Starting :mod:`tomato.daemon`
``````````````````````````````

.. note::

    For instructions on how to set **tomato** up for a first run, see the :ref:`quickstart`.

Provided a :ref:`settings file <setfile>` exists, the daemon process ``tomato-daemon`` can be started on the default *port* using:

.. code:: bash

    tomato start

The daemon keeps track of *pipelines* configured in the :ref:`device file <devfile>`, and schedules *jobs* from the queue onto them. See the :ref:`concepts flowchart <concepts>` for a more detailed overview.

.. note::

    Multiple instances of the :mod:`tomato.daemon` can be running at a single PC, provided a different *port* is specified using ``--port`` argument to ``tomato`` and ``ketchup``.

Using :mod:`~tomato.tomato`
```````````````````````````
The :mod:`tomato.tomato` executable is used to configure, start, and manage the **tomato** daemon, as well as load / eject samples to / from *pipelines* and mark them ready.

    #. **To configure** the **tomato** daemon by creating a default :ref:`settings file <setfile>`, run:

        .. code-block:: bash

            >>> tomato init

    #. **To start** the **tomato** daemon on the default port, run:

        .. code-block:: bash

            >>> tomato start

        This will read the :ref:`settings file <setfile>`, and parse the :ref:`device file <devfile>` listed within. To start the **daemon on an alternative port**, run:

        .. code-block:: bash

            >>> tomato start --port <int>

        .. warning::

            All ``tomato`` and ``ketchup`` commands intended to interact with the **tomato** daemon running on an alternative port will have to be executed with the same ``--port <int>`` argument.

    #. **To stop** the **tomato** daemon, run:

        .. code-block:: bash

            >>> tomato stop

        .. note::

            The daemon will only stop if there are no running jobs. However, a snapshot of the daemon state will be generated in any case. There is currently no clean way to stop the **tomato** daemon cleanly while jobs are running.

    #. **To reload settings** of a running **tomato** daemon, run:

        .. code-block:: bash

            >>> tomato reload

        Currently, reloading *driver* settings from the :ref:`settings file <setfile>` and managing *pipelines* and/or *devices* from the :ref:`device file <devfile>` is supported. Any *component* not present in a *pipeline* is automatically removed.

        .. note::

            The daemon will only remove *pipelines*, *devices* and *components* if they are not used by any running *job*.

    #. **To manage individual pipelines** of a running **tomato** daemon, the following commands are available:

        - For loading a sample into a *pipeline*:

            .. code-block:: bash

                >>> tomato pipeline load <pipeline> <sampleid>

            This will only succeed on *pipelines* that are empty and have no jobs running.

        - To eject any sample from a *pipeline*:

            .. code-block:: bash

                >>> tomato pipeline eject <pipeline>

            This will also succeed if the *pipeline* was already empty. It will fail if the *pipeline* has a job running.

            .. note::

                As a precaution, ejecting a sample from any *pipeline* will always mark the *pipeline* as not ready.

        - To mark a *pipeline* as ready:

            .. code-block:: bash

                >>> tomato pipeline ready <pipeline>

            This will also succeed if the *pipeline* was already ready.


Using :mod:`~tomato.ketchup`
````````````````````````````

The :mod:`tomato.ketchup` executable is used to submit *payloads* to the daemon, and to check the status of and to cancel *jobs* in the queue.

    #.  **To submit** a *job* using a *payload* contained in a :ref:`payfile`, run:

        .. code-block:: bash

            >>> ketchup submit <payload>

        The *job* will enter the queue and wait for a suitable *pipeline* to begin execution.

        .. note::

            For more information about how *jobs* are matched against *pipelines*, see the documentation of the :mod:`~tomato.daemon` module.

    #.  **To check the status** of one or several *jobs* with known ``jobids``, run:

        .. code-block:: bash

            >>> ketchup status <jobids>

        When executed without argument, the status of the whole queue will be returned. The list of possible *job* statuses is:

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

    #.  **To cancel** one or more submitted *jobs* with known ``jobids``, run:

        .. code-block:: bash

            >>> ketchup cancel <jobids>

        This will mark the *jobs* for cancellation by setting their status to ``rd``. The :mod:`tomato.daemon` will then proceed with cancelling each *job*.

*Jobs* submitted to the queue will remain in the queue until a *pipeline* meets all of the following criteria:

  - A *pipeline* where all of the ``technique_names`` specified in all :class:`Tasks` within the *payload* are matched by its ``capabilities`` must exist. Once the :mod:`tomato.daemon` finds such a *pipeline*, the status of the *job* will change to ``qw`` to indicate a suitable *pipeline* exists.
  - The matching *pipeline* must contain a *sample* with a ``samplename`` that matches the name specified in the *payload*.
  - The matching *pipeline* must be marked as ``ready``.

.. note::

    Further information about :mod:`~tomato.ketchup` is available in the documentation of the :mod:`~tomato.ketchup` module.

Machine-readable output
```````````````````````
As of ``tomato-1.0``, the outputs of :mod:`~tomato.tomato` and :mod:`~tomato.ketchup` utilities can be requested as a yaml-formatted text, by passing the ``--yaml`` (or ``-y``) command-line parameter to the executables.

Accessing output data
`````````````````````
Each *job* stores its data and logs in its own *job* folder, which is a subfolder of the ``jobs.storage`` folder specified in the :ref:`settings file <setfile>`.

.. warning::

    While "live" *job* data is available in the *job* folder in pickled form, accessing those files directly is not supported and may lead to race conditions and crashes. If you need an up-to-date data archive, request a :ref:`snapshot <snapshotting>`. If you need the current status of a *device*, probe the responsible driver process.

    Note that a *pipeline* dashboard functionality is planned for a future version of ``tomato``.


Final job data
**************
By default, all data in the *job* folder is processed to create a NetCDF file. The NetCDF files can be read using :func:`xaray.open_datatree`, returning a :class:`xarray.DataTree`.

In the root node of the :class:`~xarray.DataTree`, a copy of the full *payload* is included, serialised as a json :class:`str`. Additionally, execution-specific metadata, such as the *pipeline* ``name``, and *job* submission/execution/completion time are stored on the root node, too.

The child nodes of the :class:`~xarray.DataTree` contain the actual data from each *pipeline* *component*, unit-annotated using the CF Metadata Conventions. The node names correspond to the ``role`` that *component* fullfils in a *pipeline*.

.. note::

    As opposed to ``tomato-0.2``, in ``tomato-1.0`` we currently do not output measurement uncertainties.

Unless specified within the *payload*, the default location where these output files will be placed is the ``cwd()`` where the ``ketchup submit`` command was executed; the default filenames of the returned files are ``results.<jobid>.[zip,json]``.

.. _snapshotting:

Data snapshotting
*****************
While the *job* is running, access to an up-to-date snapshot of the data is provided by :mod:`~tomato.ketchup`:

.. code:: bash

    >>> ketchup snapshot <jobid>

This will create an up-to-date ``snapshot.<jobid>.nc`` file in the current working dir. The files are overwritten on subsequent invocations of ``ketchup snapshot``. An automated, periodic snapshotting stored in a custom location can be further configured within the *payload* of the *job*.