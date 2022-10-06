**tomato**: au-tomation without the pain!
=========================================
.. image:: https://badgen.net/badge/docs/dgbowl.github.io/grey?icon=firefox
   :target: https://dgbowl.github.io/tomato
.. image:: https://badgen.net/pypi/v/tomato/?icon=pypi
   :target: https://pypi.org/project/tomato
.. image:: https://badgen.net/github/tag/dgbowl/tomato/?icon=github
   :target: https://github.com/dgbowl/tomato

**tomato** is an instrument automation package, currently developed in the 
`Materials for Energy Conversion <https://www.empa.ch/web/s501>`_ lab at Empa. 

**tomato** includes:

- the job scheduler and queue, :mod:`tomato.daemon`, using a ``sqlite3`` as a 
  backend for IPC;
- the configuration utility :mod:`~tomato.ketchup`, modelled after PBS / SGE; 
- a set of device drivers, see the :ref:`driver library`.

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
