User guide
----------

The **tomato** package consists of three user-facing utilities:

  - the state daemon management utility, :mod:`tomato.tomato`, executed by ``tomato``,
  - the job and queue management app, :mod:`tomato.ketchup`, executed by ``ketchup``,
  - the job and queue management app, :mod:`tomato.passata`, executed by ``passata``.

Further information about the responsibilities of these utilities can be found in the `tomato developer documentation <develop_tomato.html>`_.

Starting **tomato's** daemon
````````````````````````````

.. note::
    For instructions on how to set **tomato** up for a first run, see the :ref:`quickstart`.

Provided a |setfile|_ exists, the daemon process ``tomato-daemon`` can be started on the :obj:`~tomato.DEFAULT_TOMATO_PORT` using:

.. code:: bash

    tomato start

The daemon keeps track of settings as configured in the |devfile|_ and |setfile|_, manages driver processes and pipelines, and schedules jobs from the queue onto those pipelines. See the `tomato developer documentation <develop_tomato.html>`_ for a more detailed overview.

.. note::
    Multiple instances of the tomato daemon can be running at a single PC, provided a different port is specified. This can be done using the ``--port`` argument to ``tomato``, ``ketchup``, and ``passata``.

Using the ``tomato`` executable
```````````````````````````````
The ``tomato`` executable is used to configure, start, and manage the tomato daemon, as well as load / eject samples to / from *pipelines* and mark them ready.

    #. **To configure** the tomato daemon by creating a default |setfile|_ and |devfile|_, run:

        .. code-block:: bash

            >>> tomato init

    #. **To start** the tomato daemon on the default port, run:

        .. code-block:: bash

            >>> tomato start

        This will read the |setfile|_, and parse the |devfile|_ listed within. To start the daemon on an **alternative port**, run:

        .. code-block:: bash

            >>> tomato start --port <int>

        .. warning::

            All ``tomato``, ``ketchup``, and ``passata`` commands intended to interact with the tomato daemon running on an alternative port will have to be executed with the same ``--port <int>`` argument.

    #. **To stop** the tomato daemon, run:

        .. code-block:: bash

            >>> tomato stop

        .. note::

            The daemon will only stop if there are no running jobs. There is currently no clean way to stop the tomato daemon cleanly while jobs are running.

    #. **To reload settings** of a running tomato daemon, run:

        .. code-block:: bash

            >>> tomato reload

        Currently, only modifying/adding/removing pipelines, devices, and components from the |devfile|_ is supported:

        - Any component not present in a pipeline is automatically removed.
        - Any driver with no components is stopped.
        - New pipelines, devices, components, and drivers are spawned as appropriate.

        No change at all is done if it would affect any pipeline with a running job.

        .. admonition:: TODO:

            Reloading driver settings from the |setfile|_ and passing those settings to the driver process is not yet implemented.

    #. **To manage individual pipelines** of a running tomato daemon, the following commands are available:

        - For checking the status of all configured pipelines:

            .. code-block:: bash

                >>> tomato status pipelines


        - For loading a sample into a pipeline:

            .. code-block:: bash

                >>> tomato pipeline load <pipeline> <sampleid>

            This will only succeed on pipelines that are empty and have no jobs running.

        - To eject any sample from a pipeline:

            .. code-block:: bash

                >>> tomato pipeline eject <pipeline>

            This will also succeed if the pipeline was already empty. It will fail if the pipeline has a job running.

            .. note::
                As a precaution, ejecting a sample from any pipeline will always mark the pipeline as **not ready**.

        - To mark a pipeline as ready:

            .. code-block:: bash

                >>> tomato pipeline ready <pipeline>

            This will also succeed if the pipeline was already ready.


Using the ``ketchup`` executable
````````````````````````````````
The ``ketchup`` executable is used to submit a |payfile|_ to the daemon creating new jobs, and to check the status of and to cancel jobs in the queue.

    #.  **To submit** a job using a payload contained in a |payfile|_, run:

        .. code-block:: bash

            >>> ketchup submit <payload>

        The job will enter the queue and wait for a suitable pipeline to begin execution.

        .. note::
            For more information about how jobs are matched against pipelines, see the documentation of the :mod:`~tomato.daemon` module.

    #.  **To check the status** of one or several jobs with known ``jobids``, run:

        .. code-block:: bash

            >>> ketchup status <jobids>

        When executed without argument, the status of the **whole queue** will be returned. The list of possible job statuses is:

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

        .. warning::
            If a job has been "stuck" with status ``q`` for a long time (more than 10 s), it means there is no pipeline that matches the specified payload. This is most likely due to a mismatch of :obj:`component_roles <dgbowl_schemas.tomato.payload.Task.component_role>` from the tasks in the payload with the ``component.role`` entries in the |devfile|_, or due to a mismatch of the :obj:`~dgbowl_schemas.tomato.payload.Task.technique_name` in the payload task with the capabilities of the matched component, as reported by the ``tomato-driver`` processes. Check your |payfile|_.

    #.  **To cancel** one or more submitted jobs with known ``jobids``, run:

        .. code-block:: bash

            >>> ketchup cancel <jobids>

        This will mark the jobs for cancellation by setting their status to ``rd``. The tomato daemon will then proceed with cancelling each job and creating a results file, if possible.


.. note::
    Further information about :mod:`~tomato.ketchup` is available in the documentation of the :mod:`~tomato.ketchup` module.

Job execution logic
```````````````````
Jobs submitted to the queue will remain in the queue with status ``q`` until a pipeline meets all of the following criteria:

  - A pipeline where all of the :obj:`Task.component_role <dgbowl_schemas.tomato.payload.Task.component_role>` entries from the |payfile|_ can be matched by ``component.roles`` on a single pipeline.
  - A pipeline where all of the components matching the above roles can also match the :obj:`Task.technique_name <dgbowl_schemas.tomato.payload.Task.technique_name>` in their ``capabilities``.

Once the tomato daemon finds such a pipeline, the status of the job will change to ``qw`` to indicate a suitable pipeline exists. To proceed with job execution, the daemon checks the following criteria:

  - The matching pipeline must contain a sample with a ``samplename`` that matches the :obj:`Sample.identifier <dgbowl_schemas.tomato.payload_2_2.sample.Sample.identifier>` specified in the |payfile|_.
  - The matching pipeline must be marked as ``ready``.

Machine-readable output
```````````````````````
As of ``tomato-1.0``, the outputs of the ``tomato``, ``ketchup``, and ``passata`` utilities can be requested as a yaml-formatted text, by passing the ``--yaml`` command-line parameter to the executables.

Accessing result data
`````````````````````
Each job stores its data and logs in its own job folder, which is a subfolder of the ``jobs.storage`` folder specified in the |setfile|_.

.. warning::
    While "live" job data is available in the job folder in pickled form, accessing those files directly is not supported and may lead to race conditions and crashes. If you need an up-to-date data archive, request a :ref:`snapshot <snapshotting>` using ``ketchup snapshot <jobid>``. If you need the current status of a component, probe the responsible driver process via ``passata status <name>``.

Final job data and metadata
***************************
By default, all data in the job folder is processed to create a NetCDF file. The NetCDF files can be read using :func:`xarray.open_datatree`, returning a :class:`~xarray.DataTree`. In the root node of the :class:`~xarray.DataTree`, the :obj:`~xarray.DataTree.attrs` dictionary contains all tomato-relevant metadata. This currently includes:

- ``tomato_version`` which is the version of tomato used to create the NetCDF file,
- ``tomato_Job`` which is the :obj:`~tomato.models.Job` object describing the job, serialised as a JSON :class:`str`, containing the full payload, sample information, as well as job submission/execution/completion time.

The child nodes of the :class:`~xarray.DataTree` contain:

- the actual data from each pipeline component, unit-annotated using the CF Metadata Conventions. The node names correspond to the ``component.role`` in the pipeline that executed the job.
- a ``tomato_Component`` entry in the :obj:`attrs` object, which is the :obj:`~tomato.models.Component` object describing the component, serialised as a JSON :class:`str`.

.. note::
    The ``tomato_Job`` and ``tomato_Component`` entries can be converted back to the source objects using :func:`tomato.models.Job.model_validate_json` and :func:`tomato.models.Component.model_validate_json`, respectively.

Unless specified within the payload, the default location where these output files will be placed is the working directory (``cwd``) where the ``ketchup submit`` command was executed. The default filename of the returned results file is ``results.<jobid>.nc``.

.. _snapshotting:

Data snapshotting
*****************
While the job is running, access to an up-to-date snapshot of the data is provided by ``ketchup``:

.. code:: bash

    >>> ketchup snapshot <jobid>

This will create an up-to-date ``snapshot.<jobid>.nc`` file in the current working directory. The files are overwritten on subsequent invocations of ``ketchup snapshot``. An automated, periodic snapshotting stored in a custom location can be further configured within the payload of the job.

.. caution::
    Be careful when opening snapshot files for analysis in place. If the running ``tomato-job`` process tries to overwrite a snapshot file that's open in a different process, it may lead to a crash in the snapshotting routine (especially on Windows), and the job will end with a ``ce`` status.
