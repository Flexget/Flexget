import logging
from flexget.event import event
from flexget import manager

log = logging.getLogger('db_analyze')


def analyze():
    log.info('Running ANALYZE on database to improve performance.')
    session = manager.Session()
    session.execute('ANALYZE')


# Run after the cleanup is actually finished
@event('manager.db_cleanup', 0)
def on_cleanup(session):
    # Only run in --cron mode, to prevent unneeded delays
    if manager.manager.options.quiet:
        analyze()


@event('manager.db_upgraded')
def on_upgraded(manager):
    analyze()
