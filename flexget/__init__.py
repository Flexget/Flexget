#!/usr/bin/python

import os
import sys
import logging
from flexget import logger
from flexget.options import CoreOptionParser
from flexget import plugin
from flexget.manager import Manager

__version__ = '{subversion}'

log = logging.getLogger('main')


def main():
    """Main entry point for Command Line Interface"""

    logger.initialize()

    parser = CoreOptionParser()
    plugin.load_plugins(parser)

    options = parser.parse_args()[0]

    try:
        manager = Manager(options)
    except IOError, e:
        # failed to load config, TODO: why should it be handled here? So sys.exit isn't called in webui?
        log.critical(e)
        logger.flush_logging_to_console()
        sys.exit(1)

    log_level = logging.getLevelName(options.loglevel.upper())
    log_file = os.path.expanduser(manager.options.logfile)
    # If an absolute path is not specified, use the config directory.
    if not os.path.isabs(log_file):
        log_file = os.path.join(manager.config_base, log_file)
    logger.start(log_file, log_level)

    if options.profile:
        try:
            import cProfile as profile
        except ImportError:
            import profile
        profile.runctx('manager.execute()', globals(), locals(), os.path.join(manager.config_base, 'flexget.profile'))
    else:
        manager.execute()
