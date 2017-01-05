from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os
from argparse import SUPPRESS

from flexget import options
from flexget.event import event

log = logging.getLogger('log_start')


@event('manager.startup')
def log_on_start(manager):
    if manager.options.log_start:
        log.info('FlexGet started (PID: %s)' % os.getpid())


@event('manager.shutdown')
def log_on_shutdown(manager):
    if manager.options.log_start:
        log.info('FlexGet stopped (PID: %s)' % os.getpid())


@event('options.register')
def register_options():
    options.get_parser().add_argument('--log-start', action='store_true', help=SUPPRESS)
