.. _driver_develop:

Developing **tomato** drivers
-----------------------------
As of ``tomato-1.0``, all device *drivers* are developed as separate Python packages with their own documentation and versioning. To ensure compatibility of the Manager between the ``tomato-driver`` process and the implementation of the *driver*, an abstract class :class:`~tomato.driverManager_1_0.ModelInterface` is provided. A class inheriting from this abstract class, with the name :class:`DriverManager`, **has** to be available when the selected *driver* module is imported.

.. note::

    The :class:`~tomato.driverManager_1_0.ModelInteface` is versioned. Your driver should target a single version of this Manager by inheriting from only one such abstract class. **Any deprecation notices will be provided well in advance directly to driver maintainers.** Support for :mod:`~tomato.driverManager_1_0` introduced in ``tomato-1.0`` is guaranteed until at least ``tomato-3.0``.

Bootstrapping a *driver* process
````````````````````````````````
When the *driver* process is launched (as a ``tomato-driver``), it's given information about how to connect to the ``tomato-daemon`` process and which device *driver* to spawn. Once a connection to the ``tomato-daemon`` is established, the *driver* settings are fetched, and the :class:`DriverManager` is instantiated passing any settings to the constructor. Then, all *components* on all *devices* of this *driver* type that are known to ``tomato-daemon`` are registered using the :func:`dev_register` function.

.. note::

    Each *driver* creates a separate log file for each port **tomato** has been executed with. The logfile is stored in the same location as the ``tomato-daemon`` logs, i.e. as configured under the ``jobs.storage`` option. The verbosity of the ``tomato-driver`` process is inherited from the ``tomato-daemon`` process.

Communication between *jobs* and *drivers*
``````````````````````````````````````````
After the *driver* process is bootstrapped, it enters the main loop, listening for commands to action or pass to the :class:`ModelInterface`. Therefore, if a *job* needs to submit a :class:`Task`, it passes the :class:`Task` to the ``tomato-driver`` process, which actions it on the appropriate *component* using the :func:`task_submit` function. Similarly, if a *job* decides to poll the *driver* for data, it does so using the :func:`task_data` function.

In general, methods of the :class:`ModelInterface` that are prefixed with ``dev`` deal with managing *devices* or their *components* on the *driver*, methods prefixed with ``task`` deal with managing :class:`Tasks` running or submitted to *components*, and methods without a prefix deal with configuration or status of the *driver* itself.

.. note::

    The :class:`ModelInterface` contains a sub-class :class:`DriverManager`. In general, the :class:`ModelInterface` acts as a pass-through to the (abstract) methods of the :class:`DriverManager`; e.g. :func:`ModelInterface.dev_get_attr` is a passthrough function to the appropriate :func:`DriverManager.get_attr`.

    We expect most of the work in implementing a new *driver* will actually take place in the :class:`DriverManager` class.

Currently, when a :class:`Task` is submitted to a *component*, a new :class:`Thread` is launched on that *component* that takes care of preparing the *component* (via :func:`DriverManager.prepare_task`), executing the :class:`Task` (via :func:`DriverManager.task_runner`), and periodically polling the hardware for data (via the abstract :func:`DriverManager.do_task`). As each *component* can only run one :class:`Task` at the same time, subsequently submitted :class:`Tasks` are stored in a ``task_list``, which is a :class:`Queue` used to communicate with the worker :class:`Thread`. This worker :class:`Thread` is reinstantiated at the end of every :class:`Task`.

.. note::

    Direct access to the :class:`DriverManager.data` object is not thread-safe. Therefore, a reentrant lock (:class:`RLock`) object is provided as :class:`DriverManager.datalock`. Reading or writing to the :obj:`DriverManager.data` with the exception of the :func:`get_data` and :func:`do_task` methods should be only carried out when this :obj:`datalock` is acquired, e.g. using a context manager.

.. note::

    The :class:`DriverManager.data` object is intended to cache data between :func:`get_data` calls initiated by the *job*. This object is therefore cleared whenever :func:`get_data` is called; it is the responsibility of the ``tomato-job`` process to append or store any new data.

    To access the status of the *component*, the :class:`DriverManager` provides a :func:`status` method. The implementation of what is reported as *component* status (including e.g. returning latest cached datapoint) is up to the developers of each *driver*.

Best Practices when developing a *driver*
`````````````````````````````````````````
- We follow the usual Python (PEP-8) convention of ``_``-prefixed methods and attributes considered to be private. However, there is no way to enforce such privacy in Python.
- The :func:`DriverManager.attrs` defines the variable attributes of the *component* that should be accessible, using :class:`Attr`. All entries in :func:`attrs` should be present in :obj:`DriverManager.data`. There should be no entries in :obj:`data` that are not in returned by :func:`attrs`.
- Each :class:`DriverManager` contains a link to its parent :class:`ModelInterface` in the :obj:`DriverManager.driver` object.
- Internal functions of the :class:`DriverManager` and :class:`ModelInterface` should be re-used wherever possible. E.g., reading *component* attributes should always be carried out using :func:`get_attr`.

ModelInterface ver. 1.0
```````````````````````

.. autoclass:: tomato.driverinterface_1_0.ModelInterface
    :no-index:
    :members:
