#!/usr/bin/python
from __future__ import unicode_literals, division, absolute_import, print_function

from ._version import __version__

import logging
import os
import sys

from flexget import logger, plugin
from flexget.manager import Manager
from flexget.options import get_parser

log = logging.getLogger('main')


def main(args=None):
    """Main entry point for Command Line Interface"""

    logger.initialize()

    plugin.load_plugins()

    options = get_parser().parse_args(args)

    try:
        manager = Manager(options)
    except (IOError, ValueError) as e:
        print('Could not initialize manager: %s' % e, file=sys.stderr)
        sys.exit(1)

    if options.profile:
        try:
            import cProfile as profile
        except ImportError:
            import profile
        profile.runctx('manager.start()', globals(), locals(),
                       os.path.join(manager.config_base, options.profile))
    else:
        manager.start()
