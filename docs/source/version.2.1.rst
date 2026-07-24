**tomato**-v2.1
---------------
.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.1&color=blue&logo=github
    :target: https://github.com/dgbowl/tomato/tree/2.1
.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.1&color=blue&logo=pypi
    :target: https://pypi.org/project/tomato/2.1/
.. image:: https://img.shields.io/static/v1?label=release%20date&message=2025-06-07&color=red&logo=pypi

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

Changes from ``tomato-2.0`` include:

- *Driver* processess are now better at logging errors. All ``Exceptions`` raised by the :obj:`DriverInterface` should should now be caught and logged; as functionality of the *components* should only be accessed via the :obj:`DriverInterface`, this should catch all cases.
- The :func:`cmp_measure` of each *component* can now be periodically called by the *driver* process, if a task is not running. The interval (in seconds) can be configured by the user in the *driver* section of the |setfile|_ (under ``driver.<driver_name>.idle_measurement_interval``) or provided by the driver developer (under :obj:`DriverInterface.idle_measurement_interval`); it falls back to ``None`` which means no periodic measurement will be done.
- Functions in the :mod:`tomato.passata` module that change the *component* state now check whether the *component* has a running task. If a *component* is running, a change of state (via :func:`~tomato.passata.reset` or :func:`~tomato.passata.set_attr`) can be forced by setting ``force=True``.
- A new :func:`tomato.passata.register` function (and CLI invocation ``passata register <component>``), in order to retry component registration.
- A new ``DriverInterface-2.1``, with the following changes:

  - :class:`~tomato.driverinterface_2_1.Attr` now accepts ``options``, which is the :class:`set` of values this attribute can be set to.
  - The decorators are now in :mod:`tomato.driverinterface_2_1.decorators`.
  - A new decorator, :func:`~tomato.driverinterface_2_1.decorators.coerce_val`, is provided to allow simpler type conversion and boundary checking.
  - Better error handling in ``tomato-driver`` processes; the following guidelines should be followed:

    - :class:`ValueError` or :class:`AttributeError` should be raised by the component methods when wrong vals or attrs are supplied/queried (:func:`get_attr`, :func:`set_attr`); those exception types will be caught, logged, and the ``tomato-driver`` won't crash
    - :class:`RuntimeError` should be raised by the component :func:`__init__` during component registration; this exception type will be caught, logged, and re-registration will be attempted at most 3 x in total by the ``tomato-daemon``

- A new ``Payload-2.1``, with the following changes to ``Task`` specification in ``Payload.method``:

  - ``component_tag`` is renamed to ``component_role``
  - ``task_name`` entry added, can be used to name *tasks* across a *payload* to trigger the below actions
  - ``start_with_task_name`` entry added; when specified, the parent *task* will wait until the *task* with a matching ``task_name`` is started
  - ``stop_with_task_name`` entry added; when specified, the parent *task* will stop execution once a *task* with a matching ``task_name`` is started
  - ``max_duration`` and ``sample_interval`` can be provided as :class:`str`, which will be converted to the number of seconds using :mod:`pint`

.. codeauthor::
    Peter Kraus
