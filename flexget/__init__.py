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
    logger.initialize()

    parser = CoreOptionParser()

    time_took = plugin.load_plugins(parser)
    log.debug('Plugins took %.2f seconds to load' % time_took)

    options = parser.parse_args()[0]

    try:
        manager = Manager(options)
    except IOError, e:
        # failed to load config
        log.critical(e.message)
        logger.flush()
        sys.exit(1)

    manager.acquire_lock()

    log_level = logging.getLevelName(options.loglevel.upper())
    logger.start(os.path.join(manager.config_base, 'flexget.log'), log_level, quiet=options.quiet)

    if options.doc:
        plugin.print_doc(options.doc)
    else:
        manager.execute()
