#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import os
import sys
import logging
from flexget import logger
from flexget.options import exec_parser
from flexget.ui.options import webui_parser
from flexget.ui.manager import UIManager
import flexget.ui.webui
from flexget import plugin

log = logging.getLogger('main')


def main():
    """Main entry point for FlexGet UI"""

    logger.initialize()

    # The core plugins need the exec parser to add their options to
    plugin.load_plugins(exec_parser)

    # Use the ui options parser to parse the cli
    options = webui_parser.parse_args()
    try:
        manager = UIManager(options)
    except IOError as e:
        # failed to load config
        log.critical(e.message)
        logger.flush_logging_to_console()
        sys.exit(1)

    log_level = logging.getLevelName(options.loglevel.upper())
    logger.start(os.path.join(manager.config_base, 'flexget.log'), log_level)

    # Keep the database locked for the entire time the webui is open, to be safe
    with manager.acquire_lock():
        flexget.ui.webui.start(manager)
