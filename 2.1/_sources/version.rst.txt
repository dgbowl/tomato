Version history
===============
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

**tomato**-v2.0
---------------
.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.0&color=blue&logo=github
    :target: https://github.com/dgbowl/tomato/tree/2.0
.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.0&color=blue&logo=pypi
    :target: https://pypi.org/project/tomato/2.0/
.. image:: https://img.shields.io/static/v1?label=release%20date&message=2025-02-23&color=red&logo=pypi

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

Changes from ``tomato-1.0`` include:

- *Jobs* are now tracked in a queue stored in a ``sqlite3`` database instead of on the ``tomato.daemon``.
- The ``logdir`` can now be set in |setfile|_, with the default value configurable using ``tomato init``.
- The ``tomato status`` command now supports further arguments: ``pipelines``, ``drivers``, ``devices``, and ``components`` can be used to query status of subsets of the running **tomato**.
- A new ``passata`` command and :mod:`tomato.passata` module for interacting with *components* over CLI and API.
- A new ``DriverInterface-2.0``, with the following changes:
  - :func:`cmp_constants`: an accessor for :obj:`ModelDevice.constants` and :obj:`ModelInterface.constants`, which are containers for the *driver* and *component*-specific metadata,
  - :func:`cmp_last_data`: an accessor for :obj:`ModelDevice.last_data`, which should contain the last timestamped datapoint,
  - :func:`cmp_measure`: a passthrough function to launch :func:`ModelDevice.measure`, which will trigger a one-shot measurement to populate :obj:`ModelDevice.last_data`
  - :func:`DeviceFactory`: a factory function that creates an appropriate :obj:`ModelDevice` instance.
  - Deprecation of :func:`dev_*` in favour of :func:`cmp_*`.
  - :func:`task_validate`: a validation function which verifies the provided :class:`Task` contains ``task_params`` that are compatible with the :obj:`Attrs` specified on the component.

.. codeauthor::
    Peter Kraus


**tomato**-v1.0
---------------
.. image:: https://img.shields.io/static/v1?label=tomato&message=v1.0&color=blue&logo=github
    :target: https://github.com/dgbowl/tomato/tree/1.0
.. image:: https://img.shields.io/static/v1?label=tomato&message=v1.0&color=blue&logo=pypi
    :target: https://pypi.org/project/tomato/1.0/
.. image:: https://img.shields.io/static/v1?label=release%20date&message=2024-04-01&color=red&logo=pypi

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

The code has been restructured and the interprocess communication is now using :mod:`zmq` instead of :mod:`sqlite`. The dependency on :mod:`yadg` has also been removed.

The driver library is now separate from **tomato**. A :class:`ModelInterface` class is provided to facilitate new driver development.

.. codeauthor::
    Peter Kraus


**tomato**-v0.2
---------------
.. image:: https://img.shields.io/static/v1?label=tomato&message=v0.2&color=blue&logo=github
    :target: https://github.com/dgbowl/tomato/tree/0.2
.. image:: https://img.shields.io/static/v1?label=tomato&message=v0.2&color=blue&logo=pypi
    :target: https://pypi.org/project/tomato/0.2/
.. image:: https://img.shields.io/static/v1?label=release%20date&message=2022-10-06&color=red&logo=pypi

.. sectionauthor::
    Peter Kraus

Developed in the Materials for Energy Conversion lab at Empa, in Dübendorf, with contributions from the THEOS lab at EPFL, in Lausanne.

First public release, corresponding to the code developed for the BIG-MAP Stakeholder Initiative Aurora, Deliverable D2. Includes:

- driver for BioLogic devices;
- a dummy driver for testing;
- basic scheduling/queueing functionality;
- data snapshotting and parsing.

This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement No 957189. The project is part of BATTERY 2030+, the large-scale European research initiative for inventing the sustainable batteries of the future.

.. codeauthor::
    Peter Kraus,
    Loris Ercole.

.. |setfile| replace:: *settings file*

.. _setfile: quickstart.html#settings-file