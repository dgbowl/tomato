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
- The configuration files (|setfile|_, |devfile|_) are now parsed by the :mod:`~tomato.daemon` into a new :class:`tomato.models.DeviceFile` model. This model holds the :class:`~tomato.models.Component`, :class:`~tomato.models.Device`, and :class:`~tomato.models.Driver` models that are required to build the :class:`~tomato.models.Pipeline` models.

  .. note::

    As a consequence of this change, the :mod:`~tomato.tomato` and :mod:`~tomato.passata` API has changed.

- Included a new :mod:`~tomato.driverinterface_3_0` module. The key changes here are:

  - The abstract class representing the registered components is now called :obj:`~tomato.driverinterface_3_0.ModelComponent`. The name ``"Component"`` (or ``cmp``) should now be used consistently throughout instead of ``"Device"``.
  - The :func:`ModelInterface.ComponentFactory() <tomato.driverinterface_3_0.ModelInterface.ComponentFactory>` is no longer an abstract function. By default it attempts to instantiate the :class:`Component` class in the top level of the driver module. As a consequence, the :class:`~tomato.driverinterface_3_0.ModelInterface` has no abstract methods/functions.
  - The :class:`tomato.models.Component` model now automatically generates its :obj:`Component.name <tomato.models.Component.name>`. As a consequence, the :obj:`ModelInterface.devmap <tomato.driverinterface_3_0.ModelInterface.devmap>` has the :obj:`~tomato.models.Component.name` as a key and the correct :obj:`~tomato.models.Component.name` is returned appropriately throughout the code.
  - Reworked :func:`ModelComponent.status() <tomato.driverinterface_3_0.ModelComponent.status>`, which is now an abstract function, that should now return :class:`~tomato.driverinterface_3_0.Status` objects.
  - Reworked :func:`ModelComponent.stop() <tomato.driverinterface_3_0.ModelComponent.stop>`, :func:`~tomato.driverinterface_3_0.ModelComponent.reset`, and :func:`~tomato.driverinterface_3_0.ModelComponent.quit`:

    - :func:`~tomato.driverinterface_3_0.ModelComponent.stop` is a helper function that should stop any activity on the component and bring it component into a safe state. It is called as part of :func:`ModelInterface.cmp_stop() <tomato.driverinterface_3_0.ModelInterface.cmp_stop>`, :func:`~tomato.driverinterface_3_0.ModelInterface.cmp_reset`, and  :func:`~tomato.driverinterface_3_0.ModelInterface.cmp_quit`.
    - :func:`~tomato.driverinterface_3_0.ModelComponent.reset` is a helper function that should bring the component into a state ready for new :class:`Tasks <tomato.models.Task>`. It is called after :func:`~tomato.driverinterface_3_0.ModelComponent.stop` in :func:`ModelInterface.cmp_reset() <tomato.driverinterface_3_0.ModelInterface.cmp_reset>`, at the completion of every :class:`~tomato.models.Payload`.
    - :func:`~tomato.driverinterface_3_0.ModelComponent.quit` is an abstract helper function that should ensure the component can be released by **tomato**. It is called after :func:`~tomato.driverinterface_3_0.ModelComponent.stop` in :func:`ModelInterface.cmp_quit() <tomato.driverinterface_3_0.ModelInterface.cmp_quit>`, which is called whenever the driver process exits via an :mod:`atexit` handler.


.. codeauthor::
    Peter Kraus
