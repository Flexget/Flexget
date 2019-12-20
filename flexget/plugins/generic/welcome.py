import os
import sys

from loguru import logger

from flexget.event import event
from flexget.utils.simple_persistence import SimplePersistence

__author__ = 'paranoidi'

logger = logger.bind(name='welcome')


@event('manager.lock_acquired')
def welcome_message(manager):
    # Only run for cli cron executions
    if manager.options.cli_command != 'execute' or not manager.options.cron:
        return
    persistence = SimplePersistence(plugin='welcome')
    count = persistence.setdefault('count', 5)
    if not count:
        return

    # check for old users, assume old user if db larger than 2 MB
    if count == 5 and os.stat(manager.db_filename).st_size / 1024 / 1024 >= 2:
        logger.debug('Looks like old user, skipping welcome message')
        persistence['count'] = 0
        return

    count -= 1
    scheduler = 'scheduler' if sys.platform.startswith('win') else 'crontab'
    if not count:
        logger.info(
            'FlexGet has been successfully started from {} (--cron). I hope you have {} under control now. This message will not be repeated again.',
            scheduler,
            scheduler,
        )
    else:
        logger.info(
            '%sFlexGet has been successfully started from %s (--cron). This message will be repeated %i times for your set up verification conveniences.'
            % ('Congratulations! ' if count == 4 else '', scheduler, count)
        )
    persistence['count'] = count
