Version history
===============
**tomato**-v1.1
---------------

.. sectionauthor::
     Peter Kraus

Developed at the ConCat lab at TU Berlin.

Changes from ``tomato-1.0`` include:

- *jobs* are now tracked in a queue stored in a ``sqlite3`` database instead of on the ``tomato.daemon``.
- ``logdir`` can now be set in *settings file*, with the default value configurable using ``tomato init``.
- ``tomato status`` now supports further arguments: ``--pipelines``, ``--drivers``, ``--devices``, and ``--components`` can be used to query status of subsets of the running **tomato**

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
