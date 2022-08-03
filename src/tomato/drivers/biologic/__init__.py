"""
`biologic`: Driver for BioLogic potentiostats.

This driver is a wrapper around BioLogic's `kbio` package. 

"""
import psutil
if psutil.WINDOWS:
    from .main import get_status, get_data, start_job, stop_job
