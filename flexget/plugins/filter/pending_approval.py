from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import entry_synonym
from sqlalchemy import Column, String, Unicode, Boolean, Integer, DateTime

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
        return '<PendingEntry(task_name={},title={},url={},approved={})>' \
            .format(self.task_name, self.title, self.url, self.approved)

    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'title': self.title,
            'url': self.url,
            'approved': self.approved,
            'added': self.added
        }


class PendingApproval(object):
    schema = {'type': 'boolean'}

    @staticmethod
    def _item_query(entry, task, session):
        return session.query(PendingEntry) \
            .filter(PendingEntry.task_name == task.name) \
            .filter(PendingEntry.title == entry['title']) \
            .filter(PendingEntry.url == entry['url']) \
            .first()

    def on_task_input(self, task, config):
        if not config:
            return

        approved_entries = []
        with Session() as session:
            for approved_entry in session.query(PendingEntry) \
                    .filter(PendingEntry.task_name == task.name) \
                    .filter(PendingEntry.approved == True) \
                    .all():
                e = approved_entry.entry
                e['approved'] = True
                e['immortal'] = True
                approved_entries.append(e)

        return approved_entries

    # Run after all other filters
    @plugin.priority(-255)
    def on_task_filter(self, task, config):
        if not config:
            return

        with Session() as session:
            for entry in task.entries:
                # Cache all new task entries
                if entry.get('approved'):
                    entry.accept('entry is marked as approved')
                elif not self._item_query(entry, task, session):
                    log.verbose('creating new pending entry %s', entry)
                    session.add(PendingEntry(task_name=task.name, entry=entry))
                    entry.reject('new unapproved entry, caching and waiting for approval')

    def on_task_learn(self, task, config):
        if not config:
            return
        with Session() as session:
            # Delete all accepted entries that have passed the pending phase
            for entry in task.accepted:
                if entry.get('approved'):
                    db_entry = self._item_query(entry, task, session)
                    if db_entry and db_entry.approved:
                        log.debug('deleting approved entry %s', db_entry)
                        session.delete(db_entry)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Clean unapproved entries older than 1 year
    deleted = session.query(PendingEntry).filter(PendingEntry.added < datetime.now() - timedelta(days=365)).delete()
    if deleted:
        log.info('Purged %i pending entries older than 1 year', deleted)


def list_pending_entries(session, task_name=None, approved=None, start=None, stop=None, sort_by='added',
                         descending=True):
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


@event('plugin.register')
def register_plugin():
    plugin.register(PendingApproval, 'pending_approval', api_ver=2)
