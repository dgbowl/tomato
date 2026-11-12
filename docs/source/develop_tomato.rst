Developing **tomato**
---------------------

**tomato** program flowchart
````````````````````````````
**tomato** currently contains three command line user-facing utilities/executables:

- :mod:`~tomato.tomato`, responsible for management of the ``tomato-daemon`` process,
- :mod:`~tomato.ketchup`, responsible for job submission and management, and
- :mod:`~tomato.passata`, providing an interface to the hardware via drivers and components.

These executables then internally spawn other processes, including the state daemon process ``tomato-daemon``, a ``tomato-job`` process for every running job, and a ``tomato-driver`` process for each driver type, managing all devices of a that type.

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

        jm <-.-> jobdb[(job db\nsqlite)]
        mp -.-> jobdb

        jm <-.-> pipdb[(pip db\nsqlite)]
        pm <-.-> pipdb
        mp -.-> pipdb

        dm <-.-> drvdb[(drv db\nsqlite)]
        drvdb <-.-> dst

        setf[settings file\ndevices file] ---> cfg

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

.. note::

    Note that the :mod:`tomato.daemon` process is stateless, only responsible for reading of the configuration files and spawning the *job*, *driver* and *pipeline*--management threads. All configuration and state information that should be persistently stored (i.e. survive restart of the components) is stored in a :mod:`sqlite3` database.
