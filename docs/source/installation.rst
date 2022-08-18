.. _installation:

Installation
------------
Pre-built wheels of **tomato** are available on `PyPI <https://pypi.org/project/tomato/>`_
and can be installed using:

.. code::

    pip install --pre tomato[docs,testing]

We strongly recommend installing **tomato** into a separate ``conda`` or ``venv``
environment.

.. note::

    The optional targets ``[docs]`` and ``[testing]`` will install packages required 
    for building this documentation and running the test-suite, respectively.

.. note::
    
    As currently **tomato** does not have a stable release, make sure to install 
    the latest development version using the ``--pre`` argument to ``pip``.

Testing the installation
````````````````````````
To run the test-suite, you need to first install **tomato** using the above command,
and then you need to clone the git repository, and launch ``pytest`` from within the 
created ``tomato`` folder:

.. code::

    git clone https://github.com/dgbowl/tomato.git
    cd tomato
    pytest -vv

The test-suite currently contains tests using the :mod:`~tomato.drivers.dummy` driver,
and therefore should work on all platforms.