**tomato**-v3.x
---------------

..
    .. image:: https://img.shields.io/static/v1?label=tomato&message=v2.2&color=blue&logo=github
        :target: https://github.com/dgbowl/tomato/tree/2.2
    .. image:: https://img.shields.io/static/v1?label=tomato&message=v2.2&color=blue&logo=pypi
        :target: https://pypi.org/project/tomato/2.2/
    .. image:: https://img.shields.io/static/v1?label=release%20date&message=2026-02-22&color=red&logo=pypi

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

.. warning::

   Minimum python version has been increased to ``python>=3.11`` in ``tomato-3.0``.

Changes from ``tomato-2.2`` include:

- The state of *drivers*, *components*, and *pipelines* is now stored in a :mod:`sqlite3` database for persistent storage.
- Included a new :mod:`~tomato.driverinterface_3_0` module.


.. codeauthor::
    Peter Kraus
