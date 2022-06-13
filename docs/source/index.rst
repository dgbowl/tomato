**tomato**: au-tomation without the pain!
=========================================

**tomato** is an instrument automation package, currently developed in the 
`Materials for Energy Conversion <https://www.empa.ch/web/s501>`_ at Empa. 

.. warning::

   Tomato is Windows-only. 

Currently supported hardware is:

- a Dummy device for testing
- BioLogic potentiostats via the EC-Lib library

Installation
------------
Pre-built wheels of **tomato** are available on `PyPI <https://pypi.org/project/tomato/>`_
and can be installed using:

.. code::

    pip install tomato

.. note::

    We strongly recommend installing **tomato** into a separate conda environment. 
    Additionally, **tomato** depends on ``portalocker``, which can be installed from
    conda's defaults channel. You can easily create a new conda environment and install
    the required packages using:

    .. code::

        conda create -n tomato python=3.9 portalocker git pip
        pip install tomato


Usage
-----

The **tomato** package consists of two key parts: the job scheduler app ``tomato``,
and the queue management app :mod:`~tomato.ketchup`.

Using ``tomato``
````````````````

The job scheduler ``tomato`` can be started in verbose mode for diagnostic output:

.. code:: bash

    tomato -vv

``tomato`` is used to schedule *jobs* from the *queue* onto *pipelines*. A *pipeline*
is a way of organising one or many *devices* in a single, addressable unit. In general, 
a single *pipeline* should be a digital twin composed of all *devices* neccessary to
carry out a single *payload*.

Note that only a single instance of ``tomato`` can be running at a single machine.
    
Using :mod:`~tomato.ketchup`
````````````````````````````

:mod:`~tomato.ketchup` is used to submit, check the status of, and cancel *jobs* to 
the *queue*, as well as to load or eject *samples* from *pipelines*.

To submit a *payload* to the *queue*, run:

.. code:: bash

    ketchup submit <payload>

where ``<payload>`` is a file containing the *payload* information, including
the description of the *sample*, details of the *method*, and other information
required by ``tomato``.

To check the status of the *queue* or of a *job*, run either of:

.. code:: bash

    ketchup status
    ketchup status queue
    ketchup status <jobid>

Further information about :mod:`~tomato.ketchup` is available in the documentation
of the :mod:`~tomato.ketchup` module.

Output data
-----------

By default, all data in the *job* folder is processed using ``yadg`` to create
a *datagram*, and zipped into a zip archive. This zip archive includes all raw
data files, the ``tomato_job`` log file, and a copy of the full job payload in a 
``json`` file. The *datagram* contains timestamped, unit-annotated raw data, and
included instrumental uncertainties.

The default location where this output will be placed is the ``cwd()`` where the 
``ketchup submit`` command was executed; the default filenames of the returned files 
are ``results.<jobid>.[zip,json]``.


.. toctree::
   :maxdepth: 1
   :caption: tomato autodocs
   :hidden:

   tomato
