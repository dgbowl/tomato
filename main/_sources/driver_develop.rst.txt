.. _driver_develop:

Developing **tomato** drivers
-----------------------------
Since ``tomato-1.0``, all device *drivers* are developed as separate Python packages with their own documentation and versioning. To ensure compatibility of the Manager between the ``tomato-driver`` process and the implementation of the *driver*, an abstract class :class:`~tomato.driverinterface_2_1.ModelInterface` is provided. A class inheriting from this abstract class, with the name :class:`DriverInterface`, **has** to be available when the selected *driver* module is imported.

.. note::

    The :class:`~tomato.driverinterface_2_1.ModelInterface` is versioned. Your driver should target a single version of this :class:`ModelInterface` by inheriting from only one such abstract class. **Any deprecation notices will be provided well in advance directly to driver maintainers.** Support for :mod:`~tomato.driverinterface_1_0` introduced in ``tomato-1.0`` is guaranteed until at least ``tomato-3.0``.

Bootstrapping a *driver* process
````````````````````````````````
When the *driver* process is launched (as a ``tomato-driver``), it's given information about how to connect to the ``tomato-daemon`` process and which device *driver* to spawn. Once a connection to the ``tomato-daemon`` is established, the *driver* settings (from the |setfile|_) are fetched, and the :class:`DriverInterface` is instantiated passing any settings to the constructor. By default, these settings are stored under :obj:`DriverInterface.settings`. Finally, all *components* on all *devices* of this *driver* type that are known to ``tomato-daemon`` are registered using the :func:`cmp_register` function.

.. note::

    Each *driver* creates a separate log file for each port **tomato** has been executed with. The logfile is stored in the same location as the ``tomato-daemon`` logs, i.e. as configured under the ``logdir`` option in the |setfile|_. The verbosity of the ``tomato-driver`` process is inherited from the ``tomato-daemon`` process.

*Driver*-specific settings
``````````````````````````
The following keywords in the driver-specific settings in the |setfile|_ are reserved for use by **tomato**:

- ``idle_measurement_interval``: Specifies the interval (in seconds) after which the :func:`cmp_measure` function of all *components* registered on the *driver* should be called. The :func:`cmp_measure` checks that *components* are idle, i.e. without a running :class:`Task`. Overrides any :obj:`DriverInterface.idle_measurement_interval`.


Communication between *jobs* and *drivers*
``````````````````````````````````````````
After the *driver* process is bootstrapped, it enters the main loop, listening for commands to action or pass to the :class:`DriverInterface`. Therefore, if a *job* needs to submit a :class:`Task`, it passes the :class:`Task` to the ``tomato-driver`` process, which actions it on the appropriate *component* using the :func:`task_submit` function. Similarly, if a *job* decides to poll the *driver* for data, it does so using the :func:`task_data` function.

In general, methods of the :class:`DriverInterface` that are prefixed with ``cmp_*`` deal with managing *devices* or their *components* on the *driver*, methods prefixed with ``task_*`` deal with managing :class:`Tasks` running or submitted to *components*, and methods without a prefix deal with configuration or status of the *driver* itself.

.. note::

    The :mod:`~tomato.driverinterface_2_1` contains another abstract class :class:`~tomato.driverinterface_2_1.ModelDevice`. In general, the :class:`DriverInterface` that you have to implement acts as a pass-through to the (abstract) methods of the :class:`ModelDevice`; e.g. :func:`ModelInterface.cmp_get_attr` is a passthrough function to the appropriate :func:`ModelDevice.get_attr`.

    We expect most of the work in implementing a new *driver* will actually take place in implementing the :class:`ModelDevice` class.

Currently, when a :class:`Task` is submitted to a *component*, a new :class:`Thread` is launched on that *component* that takes care of preparing the *component* (via :func:`ModelDevice.prepare_task`), executing the :class:`Task` (via :func:`ModelDevice.task_runner`), and periodically polling the hardware for data (via the abstract :func:`ModelDevice.do_task`). As each *component* can only run one :class:`Task` at the same time, subsequently submitted :class:`Tasks` are stored in an :obj:`ModelDevice.task_list`, which is a :class:`Queue` used to communicate with the worker :class:`Thread`. This worker :class:`Thread` is reinstantiated at the end of every :class:`Task`.

.. note::

    Direct access to the :class:`ModelDevice.data` object is not thread-safe. Therefore, a reentrant lock (:class:`RLock`) object is provided as :class:`ModelDevice.datalock`. Reading or writing to the :obj:`ModelDevice.data` with the exception of the :func:`ModelDevice.get_data` and :func:`ModelDevice.do_task` methods should be only carried out when this :obj:`datalock` is acquired, e.g. using a context manager.

.. note::

    The :class:`ModelDevice.data` object is intended to cache data between :func:`ModelDevice.get_data` calls initiated by the *job*. This object is therefore cleared whenever :func:`ModelDevice.get_data` is called; it is the responsibility of the ``tomato-job`` process to append or store any new data.

To access the current configuration (i.e. status) of the *component*, the :class:`ModelDevice` provides a :func:`ModelDevice.status` method. The implementation of what is reported as *component* status is up to the developers of each *driver* via the :func:`ModelDevice.attrs` function.

To access the latest data of the *component*, the :class:`ModelDevice` provides a :func:`ModelDevice.get_last_data` method. This will

Best Practices when developing a *driver*
`````````````````````````````````````````
- The :func:`ModelDevice.attrs` defines the variable attributes of the *component* that should be accessible, using :class:`Attr`. All entries in :func:`attrs` should also be present in :obj:`ModelDevice.data`, as the data likely depends on the settings of these :class:`Attrs`.
- Each :class:`ModelDevice` contains a link to its parent :class:`ModelInterface` in the :obj:`ModelDevice.driver` object.
- Internal functions of the :class:`ModelDevice` and :class:`ModelInterface` should be re-used wherever possible. E.g., reading *component* attributes should always be carried out using :func:`ModelDevice.get_attr`.
- Only certain types of Exceptions are caught and logged by the ``tomato-driver`` process:

  - The :func:`__init__` of each :class:`ModelDevice` should raise :class:`RuntimeError` if connection to the *component*/*device* was not possible. The instantiation of the *component* (via :func:`ModelInterface.cmp_register`) will be carried out automatically 3x, then it has to be done manually via ``passata register``.
  - The :func:`set_attr` and :func:`get_attr` (and others) should raise :class:`ValueError` or :class:`AttributeError` if the val/attr supplied by the user is invalid. The expectation is that when one of these Exceptions is raised, there is no change to the state of the *component*.

  Other types of Exceptions are not caught and **will** cause the ``tomato-driver`` process to crash.

DriverInterface ver. 2.1
````````````````````````

.. autoclass:: tomato.driverinterface_2_1.ModelInterface
    :no-index:
    :members:

.. autoclass:: tomato.driverinterface_2_1.ModelDevice
    :no-index:
    :members:

.. autoclass:: tomato.driverinterface_2_1.Attr
    :no-index:
    :members:


DriverInterface ver. 2.0
````````````````````````

.. autoclass:: tomato.driverinterface_2_0.ModelInterface
    :no-index:
    :members:

.. autoclass:: tomato.driverinterface_2_0.ModelDevice
    :no-index:
    :members:

DriverInterface ver. 1.0
````````````````````````

.. autoclass:: tomato.driverinterface_1_0.ModelInterface
    :no-index:
    :members:

.. |setfile| replace:: *settings file*

.. _setfile: quickstart.html#settings-file