from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import options
from flexget.event import event
from flexget.task import Task

log = logging.getLogger('check')


@event('manager.before_config_load')
def pre_check_config(manager):
    if manager.options.cli_command == 'check':
        with open(manager.config_path) as config:
            manager.pre_check_config(config.read())

def check(manager, options):
    # If we got here, there aren't any errors. :P
    log.info('Config passed check.')
    manager.shutdown()


@event('options.register')
def register_options():
    options.register_command('check', check, help='validate configuration file and print errors')
