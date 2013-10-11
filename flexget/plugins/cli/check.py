from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import options
from flexget.event import event
from flexget.task import Task

log = logging.getLogger('check')


def check(manager, options):
    tasks = [Task(manager, name) for name in manager.tasks]
    # If we got here, there aren't any errors. :P
    log.info('Config passed check.')
    manager.shutdown()


@event('options.register')
def register_options():
    options.register_command('check', check, lock_required=False, help='validate configuration file and print errors')
