.. _driver_develop:

Developing **tomato** drivers
-----------------------------
Since ``tomato-1.0``, all device drivers are developed as separate Python packages with their own documentation and versioning. To ensure compatibility between the ``tomato-driver`` process (implemented in the :mod:`tomato.daemon.driver` module) and the functionality of the driver (implemented in the driver packages), a set of abstract classes is provided by **tomato** in versioned modules, see `supported driver interface modules`_.

.. note::
    The :mod:`tomato.driverinterface_X_Y` modules are versioned, with ``X`` being the major and ``Y`` the minor version of the corresponding **tomato** release. Your driver should target a single version of this interface. The **version of your driver** should match the **version of the driver interface**, with a point release appended, if necessary:

    - ``tomato-example-counter==2.0.0`` targets :mod:`tomato.driverinterface_2_0`,
    - ``tomato-example-counter==2.1.0`` and ``==2.1.1`` both target :mod:`tomato.driverinterface_2_1`,
    - ``tomato-example-counter~=3.0.0`` targets :mod:`tomato.driverinterface_3_0`.

.. warning::
    The :mod:`tomato.driverinterface_2_1` has been deprecated in ``tomato-3.0`` and will be removed in the next release.

.. note::
    - Support for :mod:`~tomato.driverinterface_2_0` was removed in ``tomato-3.0``.
    - Support for :mod:`~tomato.driverinterface_1_0` was removed in ``tomato-2.2``.


Driver-specific settings
````````````````````````
There are two ways to specify driver-specific settings:

- The :class:`Settings` class at the top level of the driver package. This class should inherit from a :class:`tomato.driverinterface_X_Y.Settings` class (i.e. in the driver interface module). It describes the type and purpose of each setting, and can be used to supply a default value of each setting.
- The ``drivers`` section of the |setfile|_ can be used to supply user-specified overrides to the above settings, or any settings required to instantiate the driver, e.g. ``drivers.picovna.dllpath`` in the :mod:`tomato-picovna` driver.

The following settings are defined by the :class:`tomato.driverinterface_3_0.Settings` class and are therefore reserved for use by **tomato**:

- ``idle_measurement_interval``: Specifies the interval (in seconds) after which a measurement is triggered on each component registered on the driver. This is done by calling the :func:`cmp_measure` function, which checks that components are idle, i.e. without a running :class:`Task`. Defaults to ``None``, meaning that no idle measurements will be performed.
- ``lpp_timeout``: Specifies the timeout (in seconds) after which a communication attempt with this driver will be aborted. When unset, defaults to :obj:`tomato.daemon.lpp.REQ_TIMEOUT` (in seconds).

The driver-specific settings are validated against the respective :class:`Settings` classes whenever the |setfile|_ is parsed (i.e. during ``tomato start`` or ``tomato reload``).

Bootstrapping a driver process
``````````````````````````````
When the driver process is launched (as a ``tomato-driver``), it's given information about how to connect to the ``tomato-daemon`` process and which device driver to spawn. Once a connection to the ``tomato-daemon`` is established, the driver-specific settings discussed above are fetched, and the :class:`DriverInterface` is instantiated passing any settings to the constructor. These settings are then stored locally as a :class:`Settings` object under :obj:`DriverInterface.settings`.

.. note::

    Each ``tomato-driver`` process creates a separate log file for each port **tomato** has been executed with. The logfile is stored in the same location as the ``tomato-daemon`` logs, i.e. as configured under the ``logdir`` option in the |setfile|_. The verbosity of the ``tomato-driver`` process is inherited from the ``tomato-daemon`` process.

Finally, all components on all devices of each driver type, as defined in |devfile|_, are registered via :func:`~tomato.daemon.driver.tomato_driver_bootstrap` function, calling the :func:`DriverInterface.cmp_register` function. In simpler drivers, this means a :class:`Component` class (which should inherit from the :class:`ModelComponent` abstract class) is instantiated by the :obj:`DriverInterface`. The individual :obj:`Components` are stored in :obj:`DriverInterface.devmap`; each :obj:`Component` is also given a reference to the parent :obj:`DriverInterface` object, so that per-driver objects stored on the :obj:`DriverInterface` (Python modules, serial ports, etc.) can also be accessed.

Communication between jobs and drivers
``````````````````````````````````````
After the driver process is bootstrapped, it enters the main loop, listening for commands to action or pass to the :class:`DriverInterface` on its port. Therefore, if a job needs to submit a :class:`Task`, it passes the :class:`Task` to the ``tomato-driver`` process, which actions it on the appropriate component using the :func:`task_submit` function. Similarly, if a job decides to poll the driver for data, it does so using the :func:`task_data` function.

.. warning::
    The processing of the commands received via the driver port is within a ``try - except`` block. Any :class:`Exceptions` raised by the :obj:`DriverInterface` are caught, logged in the per-driver log, and otherwise ignored.

    A :class:`~tomato.models.Reply` with ``success=False`` is returned back to the command source (i.e. ``tomato-daemon``, ``tomato-job``, or functions from :mod:`tomato.passata` module).

In general, methods of the :class:`ModelInterface` class that are prefixed with ``cmp_*`` deal with managing device *components* on the driver, methods prefixed with ``task_*`` deal with managing :class:`Tasks` running or submitted to these *components*, and methods without a prefix deal with configuration or status of the *driver* itself.

.. note::
    In general, the :class:`DriverInterface(ModelInterface)`, that you have to implement, acts as a pass-through to the (abstract) methods of the :class:`Component(ModelComponent)` tbat you also have to implement. For example:

    - :obj:`ModelInterface.cmp_get_attr(name, ...)` calls :func:`ModelComponent.get_attr` on component ``name``;
    - :obj:`ModelInterface.task_stop(name, ...)` calls :func:`ModelComponent.stop_task` and :func:`ModelComponent.get_data` on component ``name``.

    We expect most of the work in implementing a new driver will actually take place in implementing the :class:`Component(ModelComponent)` class.

Task handling
`````````````
When a new :class:`Component(ModelComponent)` is instantiated, e.g. when a component is registered on a driver, a new :class:`Thread` is launched on that component (stored under :obj:`ModelComponent.thread`) running the :func:`ModelComponent.task_runner` function. When a :class:`Task` is submitted to this component, that :obj:`Thread` takes care of:

- preparing the component by setting any :obj:`ModelComponent.attrs` to the appropriate values via :func:`ModelComponent.prepare_task`,
- managing the :class:`Task` via :func:`ModelComponent.task_runner`,
- periodically polling the hardware for data using this :obj:`Thread` via :func:`ModelComponent.do_task`,
- storing the last measured datapoint under :obj:`ModelComponent.last_data` via the abstract :func:`ModelComponent.do_measure`,
- concatenating any new data into :obj:`ModelComponent.data` via :func:`ModelComponent.do_task`.

.. tip::
    Idle measurements, triggered by the ``tomato-driver`` process, as well as measurements requested via :func:`ModelInterface.cmp_measure` use the same :obj:`Thread`, but submit a special "task" that does **not** touch :obj:`ModelComponent.attrs`.

As each component can only run one :obj:`Task` at the same time, subsequently submitted :obj:`Tasks` are stored in an :obj:`ModelComponent.task_list`, which is a :class:`Queue` used to communicate between the main thread of the driver and the :obj:`Task` worker :obj:`Thread`.

.. warning::
    Direct access to the :obj:`ModelComponent.data` object is not thread-safe. Therefore, a reentrant lock (:class:`RLock` object) is provided under :obj:`ModelComponent.datalock`. Reading or writing to the :obj:`ModelComponent.data` object should be only carried out within the :func:`ModelComponent.get_data` and :func:`ModelComponent.do_task` methods, which use the :obj:`datalock`.

    If you need to touch the :obj:`ModelComponent.data` object outside these two methods, you should acquire the :obj:`datalock` first, e.g. using a context manager.

.. note::
    The :obj:`ModelComponent.data` object is intended to cache running :obj:`Task` data between :func:`ModelComponent.get_data` calls initiated by a job. This object is therefore cleared whenever :func:`ModelComponent.get_data` is called; it is the responsibility of the ``tomato-job`` process to append or store any new :obj:`Task` data.

Driver and component status
```````````````````````````
To access the current status of the driver, the :class:`ModelInterface` class provides a :func:`ModelInterface.status` function, which returns the names of the registered components when successful.

To access the current status of a component, the :func:`ModelInterface.cmp_status` function can be used, calling the :func:`ModelComponent.status` method. This function returns a :class:`Status` class, indicating connection state, component state, values of selected attrs, and any running task.

To access the latest data of the component, the :func:`ModelInterface.cmp_last_data` function can be used, calling :func:`ModelComponent.get_last_data` method.

Best practices when developing a driver
```````````````````````````````````````
- The :func:`ModelComponent.attrs` defines the variable attributes of the component that should be accessible, using :class:`Attr`. All entries in :func:`attrs` should also be present in :obj:`ModelDevice.data`, as the data likely depends on the settings of these :class:`Attrs`.
- Internal functions of the :class:`ModelComponent` and :class:`ModelInterface` should be re-used wherever possible. E.g., reading component attributes should always be carried out using :func:`ModelComponent.get_attr`.


Supported driver interface modules
``````````````````````````````````

- :mod:`tomato.driverinterface_3_0`, supported at least until **tomato** version 4.0
- :mod:`tomato.driverinterface_2_1`, deprecated in **tomato** version 3.0
