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
