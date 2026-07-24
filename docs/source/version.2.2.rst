**tomato**-v2.2
---------------

.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.2&color=blue&logo=github
    :target: https://github.com/dgbowl/tomato/tree/2.2
.. image:: https://img.shields.io/static/v1?label=tomato&message=v2.2&color=blue&logo=pypi
    :target: https://pypi.org/project/tomato/2.2/
.. image:: https://img.shields.io/static/v1?label=release%20date&message=2026-02-22&color=red&logo=pypi

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

Changes from ``tomato-2.1`` include:

- Fixes many bugs due to the :func:`cmp_measure` function race condition with running tasks.
- Introduces the "lazy pirate" pattern in ``tomato-job`` processes, which should make jobs more reliable.
- Added functionality for automatically creating RO-crates from completed jobs.
- The NetCDF export using :mod:`xarray` now uses :mod:`h5netcdf` for exporting NetCDF files, as :mod:`netcdf4` has some issues with filesystem paths.
- The deprecated :mod:`tomato.driverinterface_1_0` has been removed.

- A new ``Payload-2.2``:

  - The ``settings.snapshot.snapshot_interval`` replaces ``settings.snapshot.frequency``. The ``snapshot_interval`` can be provided as :class:`str`, which will be converted to the number of seconds using :mod:`pint`.
  - The ``sample.identifier`` replaces ``sample.name``. A new required ``user.identifier`` section
  - The ``settings.output.repositories`` entry is added, which allows users to select which repository configured in the ``settings.toml`` file will be used to upload the job data.


.. codeauthor::
    Peter Kraus
