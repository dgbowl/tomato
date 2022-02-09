"""
Main module - executables for tomato.

"""
import argparse
import logging
from importlib import metadata
import appdirs

def run_daemon():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f'%(prog)s version {metadata.version("tomato")}',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity by one level."
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="Decrease verbosity by one level."
    )
    args = parser.parse_args()
    loglevel = min(max(30 + 10 * (args.quiet - args.verbose), 10), 50)
    logging.basicConfig(level=loglevel)
    
    log = logging.getLogger(__name__)
    log.debug(f"loglevel set to '{logging._levelToName[loglevel]}'")

    dirs = appdirs.AppDirs("tomato", "dgbowl", version=metadata.version("tomato"))
    log.debug(f"local config folder: '{dirs.user_config_dir}'")
    log.debug(f"local data folder:   '{dirs.user_data_dir}'")
    log.debug(f"local log folder:    '{dirs.user_log_dir}'")