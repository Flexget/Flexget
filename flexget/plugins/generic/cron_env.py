from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import sys

from flexget.utils.log import log_once
from flexget.event import event
from flexget.utils.simple_persistence import SimplePersistence

__author__ = 'paranoidi'

log = logging.getLogger('cron_env')


@event('manager.execute.started')
def check_env(manager, options):
    persistence = SimplePersistence(plugin='cron_env')
    encoding = sys.getfilesystemencoding()
    if options.cron:
        if 'terminal_encoding' in persistence:
            terminal_encoding = persistence['terminal_encoding']
            if terminal_encoding.lower() != encoding.lower():
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
        persistence['terminal_encoding'] = encoding
