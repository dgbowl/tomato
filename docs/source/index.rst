**tomato**: au-tomation without the pain!
=========================================
.. image:: https://badgen.net/badge/docs/dgbowl.github.io/grey?icon=firefox
   :target: https://dgbowl.github.io/tomato
.. image:: https://badgen.net/pypi/v/tomato/?icon=pypi
   :target: https://pypi.org/project/tomato
.. image:: https://badgen.net/github/tag/dgbowl/tomato/?icon=github
   :target: https://github.com/dgbowl/tomato

**tomato** is an instrument automation package, currently developed at the 
`ConCat lab <https://tu.berlin/en/concat/>`_, and previously in the 
`Materials for Energy Conversion <https://www.empa.ch/web/s501>`_ lab at Empa. 

**tomato** includes:

- a daemon for pipeline management and job scheduling, :mod:`tomato.daemon`, using :mod:`zmq` and ``sqlite3``;
- the daemon and pipeline configuration utility, :mod:`tomato.tomato`;
- the job and job queue configuration utility, :mod:`~tomato.ketchup`; 
- a set of device drivers, see the :ref:`driver library`.

This project has received funding from the European Union’s Horizon 2020 research
and innovation programme under grant agreement No 957189. The project is part of
BATTERY 2030+, the large-scale European research initiative for inventing the
sustainable batteries of the future.

.. codeauthor::
    Peter Kraus,
    Loris Ercole

.. toctree::
   :maxdepth: 1
   :caption: tomato user manual

   installation
   quickstart
   usage
   version

.. _driver library:

.. toctree::
   :maxdepth: 1
   :caption: tomato driver library

   apidoc/tomato.drivers.dummy
   apidoc/tomato.drivers.biologic

.. toctree::
   :maxdepth: 1
   :caption: tomato autodocs
   :hidden:

   apidoc/tomato
