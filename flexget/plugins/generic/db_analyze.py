from __future__ import absolute_import, division, unicode_literals

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.event import event

log = logging.getLogger('db_analyze')


# Run after the cleanup is actually finished
@event('manager.db_cleanup', 0)
def on_cleanup(manager, session):
    log.info('Running ANALYZE on database to improve performance.')
    session.execute('ANALYZE')
