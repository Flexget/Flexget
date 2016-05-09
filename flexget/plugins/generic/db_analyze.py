from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.event import event

log = logging.getLogger('db_analyze')


# Run after the cleanup is actually finished
@event('manager.db_cleanup', 0)
def on_cleanup(manager, session):
    log.info('Running ANALYZE on database to improve performance.')
    session.execute('ANALYZE')
