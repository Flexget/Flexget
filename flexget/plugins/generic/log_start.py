import os
from argparse import SUPPRESS

from loguru import logger

from flexget import options
from flexget.event import event

logger = logger.bind(name='log_start')


@event('manager.startup')
def log_on_start(manager):
    if manager.options.log_start:
        logger.info('FlexGet started (PID: {})', os.getpid())


@event('manager.shutdown')
def log_on_shutdown(manager):
    if manager.options.log_start:
        logger.info('FlexGet stopped (PID: {})', os.getpid())


@event('options.register')
def register_options():
    options.get_parser().add_argument('--log-start', action='store_true', help=SUPPRESS)
