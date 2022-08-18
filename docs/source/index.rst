**tomato**: au-tomation without the pain!
=========================================

**tomato** is an instrument automation package, currently developed in the 
`Materials for Energy Conversion <https://www.empa.ch/web/s501>`_ lab at Empa. 

**tomato** includes:

- the job scheduler and queue, :mod:`tomato.daemon`, using a ``sqlite3`` backend for IPC;
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
