#!/usr/bin/python
from __future__ import unicode_literals, division, absolute_import, print_function

from ._version import __version__

import logging
import os
import sys

from flexget import logger, plugin
from flexget.manager import Manager

log = logging.getLogger('main')


def main(args=None):
    """Main entry point for Command Line Interface"""

    try:
        logger.initialize()

        try:
            manager = Manager(args)
        except (IOError, ValueError) as e:
            print('Could not instantiate manager: %s' % e, file=sys.stderr)
            sys.exit(1)

        try:
            if manager.options.profile:
                try:
                    import cProfile as profile
                except ImportError:
                    import profile
                profile.runctx('manager.start()', globals(), locals(),
                               os.path.join(manager.config_base, manager.options.profile))
            else:
                manager.start()
        except (IOError, ValueError) as e:
            print('Could not start manager: %s' % e, file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        print('Killed with keyboard interrupt.', file=sys.stderr)
        sys.exit(1)
