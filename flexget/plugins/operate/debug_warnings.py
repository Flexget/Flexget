import warnings

from loguru import logger

from flexget import options
from flexget.event import EventType, event

logger = logger.bind(name='debug_warnings')


@event(EventType.manager__startup)
def debug_warnings(manager):
    if manager.options.debug_warnings:
        logger.info('All warnings will be raised as errors for debugging purposes.')
        warnings.simplefilter('error')


@event(EventType.options__register)
def register_parser_arguments():
    options.get_parser().add_argument(
        '--debug-warnings',
        action='store_true',
        help='elevate warnings to errors for debugging purposes, so a traceback is shown',
    )
