#!/usr/bin/python

import os
import sys
import logging
from flexget import logger
from flexget.options import CoreOptionParser
from flexget.ui.options import UIOptionParser
from flexget.ui.manager import UIManager
import flexget.ui.webui
from flexget import plugin

log = logging.getLogger('main')


def main():
    logger.initialize()

    # The core plugins need a core parser to add their options to
    core_parser = CoreOptionParser()
    time_took = plugin.load_plugins(core_parser)

    log.debug('Plugins took %.2f seconds to load' % time_took)

    # Use the ui options parser to parse the cli
    parser = UIOptionParser(core_parser)
    options = parser.parse_args()[0]
    try:
        manager = UIManager(options, core_parser)
    except IOError, e:
        # failed to load config
        log.exception(e.message)
        logger.flush()
        sys.exit(1)

    manager.acquire_lock()

    log_level = logging.getLevelName(options.loglevel.upper())
    logger.start(os.path.join(manager.config_base, 'flexget.log'), log_level, quiet=options.quiet)

    flexget.ui.webui.start(manager)
