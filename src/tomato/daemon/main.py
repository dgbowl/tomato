from typing import Callable
import textwrap
import logging
log = logging.getLogger(__name__)

from ..drivers import driver_worker

def main_loop(
    settings: dict, 
    pipelines: dict, 
    queue: Callable, 
    state: Callable
) -> None:
    for pname, pvals in pipelines.items():
        print(f'driver_worker(settings, pvals, None): with {pname}')
        driver_worker(settings, pvals, None)
    