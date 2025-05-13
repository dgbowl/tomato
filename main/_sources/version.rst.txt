Version history
===============
**tomato**-next
---------------

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

Changes from ``tomato-2.0`` include:

- *Driver* processess are now better at logging errors. All ``Exceptions`` raised by the :obj:`DriverInterface` should should now be caught and logged; as functionality of the *components* should only be accessed via the :obj:`DriverInterface`, this should catch all cases.
- The :func:`do_measure` of each *component* can now be periodically called by the *driver* process, if a task is not running. The interval (in seconds) can be configured by the user in the *driver* section of the :ref:`*settings file* <setfile>` (under ``driver.<driver_name>.idle_measurement_interval``) or provided by the driver developer (under :obj:`DriverInterface.idle_measurement_interval`); it falls back to ``None`` which means no periodic measurement will be done.
- A new ``DriverInterface-2.1``, with the following changes:
  - :class:`~tomato.driverinterface_2_1.Attr` now accepts ``options``, which is the :class:`set` of values this attribute can be set to.
  - The decorators are now in :mod:`tomato.driverinterface_2_1.decorators`
  - A new decorator, :func:`~tomato.driverinterface_2_1.decorators.coerce_val`, is provided to allow simpler type conversion and boundary checking.

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
- The ``logdir`` can now be set in *settings file*, with the default value configurable using ``tomato init``.
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
