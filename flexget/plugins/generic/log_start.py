import os
from argparse import SUPPRESS

from loguru import logger

from flexget import options
from flexget.event import EventType, event

logger = logger.bind(name='log_start')


@event(EventType.manager__startup)
def log_on_start(manager):
    if manager.options.log_start:
        logger.info('FlexGet started (PID: {})', os.getpid())


@event(EventType.manager__shutdown)
def log_on_shutdown(manager):
    if manager.options.log_start:
        logger.info('FlexGet stopped (PID: {})', os.getpid())


@event(EventType.options__register)
def register_options():
    options.get_parser().add_argument('--log-start', action='store_true', help=SUPPRESS)
