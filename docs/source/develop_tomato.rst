Developing **tomato**
---------------------

.. important::
    No LLM / No generative AI policy. This means:

    - Do not generate issues using LLMs.
    - Do not use LLMs for patches / pull requests.
    - Do not submit LLM-generated comments on the issue tracker.

   For further reasoning, please refer to `Johannes Link's excellent blog on this issue <https://blog.johanneslink.net/2025/11/04/to-gen-or-not-to-gen/>`_.

**tomato** program flowchart
````````````````````````````
**tomato** currently contains three command line user-facing utilities/executables:

- :mod:`~tomato.tomato`, responsible for management of the ``tomato-daemon`` process,
- :mod:`~tomato.ketchup`, responsible for job submission and management, and
- :mod:`~tomato.passata`, providing an interface to the hardware by communicating to drivers and components.

These executables then internally spawn other processes, including the state daemon process ``tomato-daemon``, a ``tomato-job`` process for every running job, and a ``tomato-driver`` process for each driver type, managing all devices of a that type. An incomplete program flowchart is shown below, with the individual components discussed further below.

.. mermaid::

    flowchart TB
        subgraph daemon[tomato-daemon]
            cmd{{port:cmd}} <==> cfg[(config)]
            cfg --> jm([job manager])
            cfg --> pm([pip manager])
            cfg --> dm([driver manager])

        end

        jm -.-> job

        subgraph job[tomato-job]
            mp([main loop]) --> tp>task process]
        end

        jm <-.-> jobdb[(job db<br/>sqlite)]
        mp -.-> jobdb

        jm <-.-> pipdb[(pip db<br/>sqlite)]
        pm <-.-> pipdb
        mp -.-> pipdb

        dm <-.-> drvdb[(drv db<br/>sqlite)]
        drvdb <-.-> dst

        setf[settings file<br/>devices file] ---> cfg

        t>tomato] -.-> cmd
        k>ketchup] -.-> cmd

        dst -.-> driver
        dm -..-> driver
        tp -.-> dcmd

        subgraph driver[tomato-driver]
            dcmd{{port:cmd}} ==>  dst[(state)]
        end

        dst o-.-o h1[hardware]

        p>passata] -.-> cmd
        p -.-> dcmd

``tomato`` utility
``````````````````
This utility can:

- manage the **tomato** installation by creating default configuration files (|setfile|_, |devfile|_) via ``tomato init``,
- start the ``tomato-daemon`` process or trigger its configuration reload via ``tomato start`` and ``tomato reload``,
- manage the pipeline ``sample`` and ``ready`` state by interacting with the ``pip db`` via ``tomato pipeline``,
- retrieve the status of the ``tomato-daemon`` process (i.e. its configuration) via ``tomato status tomato``,
- retrieve the status of pipelines, drivers, devices, or components by querying the ``pip db``, ``drv db``, and ``tomato-driver`` processes via ``tomato status pipelines`` etc.

``ketchup`` utility
```````````````````
The utility first retrieves configuration from a running ``tomato-daemon``, in order to find locations of the necessary files. Then, it can:

- manage the job submission, status, cancellation by interacting with ``job db``,
- manage job snapshotting by traversing the job storage folder.

.. tip::
    This utility is modelled after common HPC queueing software, including the sub-commands (``submit``, ``cancel``, ``status``) and status codes (e.g. ``q``, ``r``, etc.).

``passata`` utility
```````````````````
The utility first retrieves configuration from a running ``tomato-daemon``, in order to find ports of running ``tomato-drivers``. Then, it can:

- register a new component on a driver,
- query the status of a component,
- query attributes, capabilities, constants on a component,
- get and set attribute values on a component,
- trigger measurements on a component,
- fetch the last measured data from a component
- trigger a reset on a component.

.. tip::
    The `marinara <https://github.com/dgbowl/marinara/>`_ package, which is the web dashboard of the **tomato** ecosystem, uses the :mod:`tomato.passata` API extensively. The CLI interface is currently not as flexible as the API.

``tomato-daemon`` process
`````````````````````````
The ``tomato-daemon`` process is stateless, only responsible for reading of the configuration files, validating driver settings, and spawning the *job*, *driver* and *pipeline*--management threads. All configuration and state information that should be persistently stored (i.e. survive restart of these components) is stored in a :mod:`sqlite3` database.

``tomato.daemon.driver.manager`` thread
.......................................
This thread ensures that the drivers, as specified in the |devfile|_ and parsed by ``tomato-daemon``, have corresponding ``tomato-driver`` process launched, re-spawned as necessary, and terminated (gracefully or forcefully) once the ``tomato-daemon`` process is about to quit. It also ensures the ``drv db`` is consistent with the running ``tomato-daemon`` processes.

The individual driver state, as stored in the ``drv db``, is also managed in this thread, taking care of heartbeating, ``tomato-driver`` spawn retries, or pruning of the ``drv db`` entries if necessary.

Finally, once a new ``tomato-driver`` process sets its ``port`` and ``pid``, this thread instructs the ``tomato-driver`` to register its components, if there are none registered so far.

``tomato.daemon.job.manager`` thread
....................................
This thread ensures that the ``job db`` and the ``tomato-job`` processes are consistent:

- New jobs, submitted via ``ketchup`` and stored in ``job db``, are matched against the existing pipelines considering the capabilities of the components and the sample in the pipeline. The job status is updated to ``qw`` accordingly.
- If an appropriate pipeline becomes ready, new ``tomato-job`` processes are launched,  the pipeline is "reserved" for this job by storing its ``jobid`` in the ``pip db``, and the job status is updated to ``r`` in the ``job db`` accordingly.
- Running jobs with inconsistent entries in the ``job db``, (e.g. missing ``tomato-job`` process with a known ``pid``) are cleared appropriately, by resetting their ``pid`` in the ``job db``.
- Jobs flagged for cancellation by ``ketchup`` are terminated appropriately and their ``job db`` entry is updated accordingly.

.. note::
    The manager thread acts on a snapshot of the ``pip db`` state, which is updated once per manager main loop, in order to ensure sequential jobs targetting the same pipeline are submitted in the correct order.

``tomato.daemon.pip.manager`` thread
....................................
This thread ensures that the ``pip db`` state is consistent with the running ``tomato-job`` processes. As mentioned above, the ``pip db`` stores a ``jobid`` for every job that should be running. Using the ``job db``, this ``jobid`` allows a lookup of job ``pids`` for all jobs that occupy a pipeline. If a ``tomato-job`` process under this stored ``pid`` no longer exists, or exists and is a zombie, the individual components of that pipeline are reset via their ``tomato-driver`` processes and the ``jobid`` in ``pip db`` is cleared.
