"""
This driver is a wrapper around BioLogic's :mod:`~tomato.drivers.biologic.kbio` package.

.. note::

    This driver is Windows-only.

Driver Configuration
--------------------
The :mod:`~tomato.drivers.biologic` driver requires the following settings in the
:ref:`setfile`:

- ``[drivers.biologic.dllpath]`` pointing to the folder of the EC-Lib Development library;
- ``[drivers.biologic.lockfile]`` pointing to a file to be used as a lock file for the DLL.

Supported *method* parameters:
---------------------------------

General parameters
``````````````````
===================== ========================================= ==========================================================
Parameter             Type                                      Meaning
===================== ========================================= ==========================================================
``technique``         |biologic.techs|                          see below
``time``              :class:`Union[int,float]`                 total runtime of the *method*, in ``s``
``I_range``           |biologic.Iranges|                        maximum current available to the *method*
``E_range``           |biologic.Eranges|                        voltage range used by the *method*
``record_every_dt``   :class:`Union[int,float]`                 delay between datapoints, in ``s``
``is_delta``          :class:`bool = False`                     is the setpoint a delta (``True``) or absolute (``False``)
===================== ========================================= ==========================================================


.. _technique limits:

Technique limits
````````````````
===================== ========================================= ===========================================================
Parameter             Type                                      Meaning
===================== ========================================= ===========================================================
``limit_current_max`` :class:`Union[int,float,str]`             maximum allowed current, can be a C-rate
``limit_current_min`` :class:`Union[int,float,str]`             minimum allowed current, can be a C-rate
``limit_voltage_max`` :class:`Union[int,float]`                 maximum allowed voltage
``limit_voltage_min`` :class:`Union[int,float]`                 minimum allowed voltage
``exit_on_limit``     :class:`bool = False`                     abort when limit reached (``True``) or continue (``False``) 
===================== ========================================= ===========================================================

Controlled current and voltage techniques
`````````````````````````````````````````
==================== ========================================= =============================================
Parameter            Type                                      Meaning
==================== ========================================= =============================================
``current``          :class:`Union[int,float,str]`             current setpoint, can be a C-rate, in ``A``
``record_every_dE``  :class:`Union[int,float]`                 maximum spacing between datapoints, in ``V``
``voltage``          :class:`Union[int,float]`                 voltage setpoint, in ``V``
``record_every_dI``  :class:`Union[int,float]`                 maximum spacing between datapoints, in ``A``
``scan_rate``        :class:`float`                            sweep rate of setpoint, in ``V/s`` or ``A/s``
==================== ========================================= =============================================

Loop parameters
```````````````
==================== ========================================= =============================================
Parameter            Type                                      Meaning
==================== ========================================= =============================================
``n_gotos``          :class:`int = 0`                          number of jumps - ``0`` means no looping.
``goto``             :class:`int`                              zero-indexed index of the *method* to jump to
==================== ========================================= =============================================

Supported ``techniques``:
`````````````````````````
- ``open_circuit_voltage``: Measure the OCV of the cell. Supports the following parameters:
    - ``time``
    - ``record_every_dt`` and ``record_every_dE``
    - ``I_range`` and ``E_range``
- ``constant_current``: Run a cell in CC mode - chronopotentiometry. Supports the following parameters:
    - ``time``
    - ``current`` and ``is_delta``
    - ``record_every_dt`` and ``record_every_dE``
    - all of the :ref:`technique limits`.
- ``constant_voltage``: Run a cell in CV mode - chronoamperometry. Supports the following parameters:
    - ``time``
    - ``voltage`` and ``is_delta``
    - ``record_every_dt`` and ``record_every_dI``
    - all of the :ref:`technique limits`.
- ``sweep_current``: Run a cell in LSC mode - linear sweep of current. Supports the following parameters:
    - ``time``
    - ``current``, ``scan_rate`` and ``is_delta``
    - ``record_every_dt`` and ``record_every_dE``
    - all of the :ref:`technique limits`.
- ``sweep_voltage``: Run a cell in LSV mode - linear sweep of voltage. Supports the following parameters:
    - ``time``
    - ``voltage``, ``scan_rate`` and ``is_delta``
    - ``record_every_dt`` and ``record_every_dI``
    - all of the :ref:`technique limits`.
- ``loop``: Arbitrary loop of techniques. Supports the following parameters:
    - ``n_gotos`` and ``goto``

.. codeauthor::
    Peter Kraus

.. |biologic.techs| replace:: :class:`Literal["constant_current", "constant_voltage", "sweep_current", "sweep_voltage", "open_circuit_voltage", "loop"]`

.. |biologic.Iranges| replace:: :class:`Literal["100 pA", "1 nA", "10 nA", "100 nA", "1 uA", "10 uA", "100 uA", "1 mA", "10 mA", "100 mA", "1 A"]`

.. |biologic.Eranges| replace:: :class:`Literal["+-2.5 V", "+-5.0 V", "+-10 V"]`

"""
from .main import get_status, get_data, start_job, stop_job
