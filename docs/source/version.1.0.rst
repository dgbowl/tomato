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
