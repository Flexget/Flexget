"""Logging utilities"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import hashlib
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, DateTime, Index

from flexget.utils.database import with_session
from flexget import db_schema
from flexget import logger as f_logger
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.event import event

log = logging.getLogger('util.log')
Base = db_schema.versioned_base('log_once', 0)


@db_schema.upgrade('log_once')
def upgrade(ver, session):
    if ver is None:
        log.info('Adding index to md5sum column of log_once table.')
        table = table_schema('log_once', session)
        Index('log_once_md5sum', table.c.md5sum, unique=True).create()
        ver = 0
    return ver


class LogMessage(Base):
    """Declarative"""

    __tablename__ = 'log_once'

    id = Column(Integer, primary_key=True)
    md5sum = Column(String, unique=True)
    added = Column(DateTime, default=datetime.now())

    def __init__(self, md5sum):
        self.md5sum = md5sum

    def __repr__(self):
        return "<LogMessage('%s')>" % self.md5sum


@event('manager.db_cleanup')
def purge(manager, session):
    """Purge old messages from database"""
    old = datetime.now() - timedelta(days=365)

    result = session.query(LogMessage).filter(LogMessage.added < old).delete()
    if result:
        log.verbose('Purged %s entries from log_once table.' % result)


@with_session
def log_once(message, logger=logging.getLogger('log_once'), once_level=logging.INFO, suppressed_level=f_logger.VERBOSE,
             session=None):
    """
    Log message only once using given logger`. Returns False if suppressed logging.
    When suppressed, `suppressed_level` level is still logged.
    """
    # If there is no active manager, don't access the db
    from flexget.manager import manager
    if not manager:
        log.warning('DB not initialized. log_once will not work properly.')
        logger.log(once_level, message)
        return

    digest = hashlib.md5()
    digest.update(message.encode('latin1', 'replace'))  # ticket:250
    md5sum = digest.hexdigest()

    # abort if this has already been logged
    if session.query(LogMessage).filter_by(md5sum=md5sum).first():
        logger.log(suppressed_level, message)
        return False

    row = LogMessage(md5sum)
    session.add(row)

    logger.log(once_level, message)
    return True
