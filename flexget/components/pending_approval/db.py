from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Unicode, Boolean, Integer, DateTime

from flexget import db_schema
from flexget.event import event
from flexget.utils.database import entry_synonym

log = logging.getLogger('pending_approval')
Base = db_schema.versioned_base('pending_approval', 0)


class PendingEntry(Base):
    __tablename__ = 'pending_entries'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_name = Column(Unicode)
    title = Column(Unicode)
    url = Column(String)
    approved = Column(Boolean)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')
    added = Column(DateTime, default=datetime.now)

    def __init__(self, task_name, entry):
        self.task_name = task_name
        self.title = entry['title']
        self.url = entry['url']
        self.approved = False
        self.entry = entry

    def __repr__(self):
        return '<PendingEntry(task_name={},title={},url={},approved={})>'.format(
            self.task_name, self.title, self.url, self.approved
        )

    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'title': self.title,
            'url': self.url,
            'approved': self.approved,
            'added': self.added,
        }


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Clean unapproved entries older than 1 year
    deleted = (
        session.query(PendingEntry)
        .filter(PendingEntry.added < datetime.now() - timedelta(days=365))
        .delete()
    )
    if deleted:
        log.info('Purged %i pending entries older than 1 year', deleted)


def list_pending_entries(
    session, task_name=None, approved=None, start=None, stop=None, sort_by='added', descending=True
):
    log.debug('querying pending entries')
    query = session.query(PendingEntry)
    if task_name:
        query = query.filter(PendingEntry.task_name == task_name)
    if approved is not None:
        query = query.filter(PendingEntry.approved == approved)
    if descending:
        query = query.order_by(getattr(PendingEntry, sort_by).desc())
    else:
        query = query.order_by(getattr(PendingEntry, sort_by))
    return query.slice(start, stop).all()


def get_entry_by_id(session, entry_id):
    return session.query(PendingEntry).filter(PendingEntry.id == entry_id).one()
