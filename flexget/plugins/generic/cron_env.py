from __future__ import unicode_literals, division, absolute_import
from flexget.utils.log import log_once

__author__ = 'paranoidi'

import sys
from flexget.utils.simple_persistence import SimplePersistence
from flexget.plugin import register_plugin
import logging

log = logging.getLogger('cron_env')


class CronEnvPlugin(object):

    def __init__(self, ):
        self.executed = False
        self.persistence = SimplePersistence(plugin='cron_env')

    def on_process_start(self, task, entries):
        if self.executed:
            return

        encoding = sys.getfilesystemencoding()
        if task.manager.options.quiet:
            if 'terminal_encoding' in self.persistence:
                terminal_encoding = self.persistence['terminal_encoding']
                if terminal_encoding != encoding:
                    log.warning('Your cron environment has different filesystem encoding '
                                '(%s) compared to your terminal environment (%s).' %
                                (encoding, terminal_encoding))
                    if encoding == 'ANSI_X3.4-1968':
                        log.warning('Your current cron environment results filesystem encoding ANSI_X3.4-1968 '
                                    'which supports only ASCII letters in filenames.')
                else:
                    log_once('Good! Your crontab environment seems to be same as terminal.')
            else:
                log.info('Please run FlexGet manually once for environment verification purposes.')
        else:
            log.debug('Encoding %s stored' % encoding)
            self.persistence['terminal_encoding'] = encoding
        self.executed = True


if not sys.platform.startswith('win'):
    register_plugin(CronEnvPlugin, 'cron_env', api_ver=2, builtin=True)
