import sys

sys.path += sys.modules["tomato"].__path__

from .main import run_tomato, run_ketchup

from . import _version
__version__ = _version.get_versions()['version']
