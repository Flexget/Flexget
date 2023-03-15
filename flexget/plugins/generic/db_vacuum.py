from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.exc import OperationalError

from flexget.event import event
from flexget.manager import Session
from flexget.utils.simple_persistence import SimplePersistence

logger = logger.bind(name='db_vacuum')
VACUUM_INTERVAL = timedelta(weeks=24)  # 6 months


# Run after the cleanup is actually finished, but before analyze
@event('manager.db_vacuum', 1)
def on_cleanup(manager):
    # Vacuum can take a long time, and is not needed frequently
    persistence = SimplePersistence('db_vacuum')
    last_vacuum = persistence.get('last_vacuum')
    if not last_vacuum or last_vacuum < datetime.now() - VACUUM_INTERVAL:
        logger.info('Running VACUUM on database to improve performance and decrease db size.')
        with Session() as session:
            try:
                session.execute('VACUUM')
            except OperationalError as e:
                # Does not work on python 3.6, github issue #1596
                logger.error('Could not execute VACUUM command: {}', e)
            else:
                persistence['last_vacuum'] = datetime.now()
