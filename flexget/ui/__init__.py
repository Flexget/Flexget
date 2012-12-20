#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import os
import sys
import logging
from flexget import logger
from flexget.options import CoreArgumentParser
from flexget.ui.options import UIArgumentParser
from flexget.ui.manager import UIManager
import flexget.ui.webui
from flexget import plugin

log = logging.getLogger('main')


def main():
    """Main entry point for FlexGet UI"""

    logger.initialize()

    # The core plugins need a core parser to add their options to
    core_parser = CoreArgumentParser()
    plugin.load_plugins(core_parser)

    # Use the ui options parser to parse the cli
    parser = UIArgumentParser(core_parser)
    options = parser.parse_args()
    try:
        manager = UIManager(options, core_parser)
    except IOError as e:
        # failed to load config
        log.critical(e.message)
        logger.flush_logging_to_console()
        sys.exit(1)

    log_level = logging.getLevelName(options.loglevel.upper())
    logger.start(os.path.join(manager.config_base, 'flexget.log'), log_level)

    flexget.ui.webui.start(manager)
