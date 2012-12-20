from __future__ import unicode_literals, division, absolute_import
import os

__author__ = 'paranoidi'

import sys
from flexget.utils.simple_persistence import SimplePersistence
from flexget.plugin import register_plugin
import logging

log = logging.getLogger('welcome')


class WelcomePlugin(object):

    def __init__(self, ):
        self.executed = False
        self.persistence = SimplePersistence(plugin='welcome')

    def on_process_start(self, task, entries):
        if self.executed or not task.manager.options.quiet:
            return
        count = self.persistence.setdefault('count', 5)
        if not count:
            return

        # check for old users, assume old user if db larger than 2 MB
        if count == 5 and os.stat(task.manager.db_filename).st_size / 1024 / 1024 >= 2:
            log.debug('Looks like old user, skipping welcome message')
            self.persistence['count'] = 0
            return

        count -= 1
        scheduler = 'scheduler' if sys.platform.startswith('win') else 'crontab'
        if not count:
            log.info('FlexGet has been successfully started from %s (--cron). '
                     'I hope you have %s under control now. This message will not be repeated again.' %
                     (scheduler, scheduler))
        else:
            log.info('%sFlexGet has been successfully started from %s (--cron). '
                     'This message will be repeated %i times for your set up verification conveniences.' %
                     ('Congratulations! ' if count == 4 else '',
                      scheduler, count))
        self.persistence['count'] = count
        self.executed = True

register_plugin(WelcomePlugin, 'welcome', builtin=True, api_ver=2)
