from loguru import logger

from flexget.event import EventType, event

logger = logger.bind(name='db_analyze')


# Run after the cleanup is actually finished
@event(EventType.manager__db_cleanup, 0)
def on_cleanup(manager, session):
    logger.info('Running ANALYZE on database to improve performance.')
    session.execute('ANALYZE')
