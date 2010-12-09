#!/usr/bin/python

from flexget import logger
from flexget.options import CoreOptionParser, UIOptionParser
from flexget.manager import Manager
from flexget import plugin
import os
import sys
import logging

__version__ = '{subversion}'

log = logging.getLogger('main')


def main(webui=False):
    logger.initialize()

    parser = CoreOptionParser()
    time_took = plugin.load_plugins(parser)

    log.debug('Plugins took %.2f seconds to load' % time_took)

    # Use a separate options parser for the webui
    if webui:
        # Get the default options from the core options parser
        options = parser.get_default_values()
        # Update the default core options with the ui options parsed from command line
        options._update(UIOptionParser().parse_args()[0].__dict__, 'loose')
    else:
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
    elif webui:
        import flexget.webui
        flexget.webui.start(manager)
    else:
        manager.execute()


def webui_main():
    """The entry point for the flexget-webui script"""
    main(webui=True)
