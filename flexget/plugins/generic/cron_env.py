import sys

from loguru import logger

from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.simple_persistence import SimplePersistence

__author__ = 'paranoidi'

logger = logger.bind(name='cron_env')


@event('manager.execute.started')
def check_env(manager, options):
    persistence = SimplePersistence(plugin='cron_env')
    encoding = sys.getfilesystemencoding()
    if options.cron:
        if 'terminal_encoding' in persistence:
            terminal_encoding = persistence['terminal_encoding']
            if terminal_encoding.lower() != encoding.lower():
                logger.warning(
                    'Your cron environment has different filesystem encoding ({}) compared to your terminal environment ({}).',
                    encoding,
                    terminal_encoding,
                )
                if encoding == 'ANSI_X3.4-1968':
                    logger.warning(
                        'Your current cron environment results filesystem encoding ANSI_X3.4-1968 '
                        'which supports only ASCII letters in filenames.'
                    )
            else:
                log_once('Good! Your crontab environment seems to be same as terminal.')
        else:
            logger.info('Please run FlexGet manually once for environment verification purposes.')
    else:
        logger.debug('Encoding {} stored', encoding)
        persistence['terminal_encoding'] = encoding
