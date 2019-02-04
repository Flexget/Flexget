from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy.schema import Index

from flexget import db_schema
from flexget.event import event
from flexget.utils.sqlalchemy_utils import table_add_column

SCHEMA_VER = 3
FAIL_LIMIT = 100

log = logging.getLogger('failed.db')
Base = db_schema.versioned_base('failed', SCHEMA_VER)


@db_schema.upgrade('failed')
def upgrade(ver, session):
    if ver is None or ver < 1:
        raise db_schema.UpgradeImpossible
    if ver == 1:
        table_add_column('failed', 'reason', Unicode, session)
        ver = 2
    if ver == 2:
        table_add_column('failed', 'retry_time', DateTime, session)
        ver = 3
    return ver


class FailedEntry(Base):
    __tablename__ = 'failed'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    tof = Column(DateTime)
    reason = Column(Unicode)
    count = Column(Integer, default=1)
    retry_time = Column(DateTime)

    def __init__(self, title, url, reason=None):
        self.title = title
        self.url = url
        self.reason = reason
        self.tof = datetime.now()

    def __str__(self):
        return '<Failed(title=%s)>' % self.title

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'added_at': self.tof,
            'reason': self.reason,
            'count': self.count,
            'retry_time': self.retry_time,
        }


# create indexes, used when creating tables
columns = Base.metadata.tables['failed'].c
Index('failed_title_url', columns.title, columns.url, columns.count)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Delete everything older than 30 days
    session.query(FailedEntry).filter(
        FailedEntry.tof < datetime.now() - timedelta(days=30)
    ).delete()
    # Of the remaining, always keep latest 25. Drop any after that if fail was more than a week ago.
    keep_num = 25
    keep_ids = [
        fe.id for fe in session.query(FailedEntry).order_by(FailedEntry.tof.desc())[:keep_num]
    ]
    if len(keep_ids) == keep_num:
        query = session.query(FailedEntry)
        query = query.filter(FailedEntry.id.notin_(keep_ids))
        query = query.filter(FailedEntry.tof < datetime.now() - timedelta(days=7))
        query.delete(synchronize_session=False)


def get_failures(session, count=None, start=None, stop=None, sort_by=None, descending=None):
    query = session.query(FailedEntry)
    if count:
        return query.count()
    if descending:
        query = query.order_by(getattr(FailedEntry, sort_by).desc())
    else:
        query = query.order_by(getattr(FailedEntry, sort_by))
    return query.slice(start, stop).all()
