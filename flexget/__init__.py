#!/usr/bin/python

from flexget import logger
from flexget.options import OptionParser
from flexget.manager import Manager
from flexget import plugin
import re
import os
import os.path
import sys
import logging

__version__ = '{subversion}'

log = logging.getLogger('main')


def main():
    logger.initialize()

    parser = OptionParser()
    time_took = plugin.load_plugins(parser)

    log.debug('Plugins took %.2f seconds to load' % time_took)

    options = parser.parse_args()[0]

    if options.version:
        print 'FlexGet %s' % __version__
        return

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
    elif options.webui:
        import webui
        webui.start(manager)
    else:
        manager.execute()
