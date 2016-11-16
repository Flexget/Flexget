from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

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


class PendingApproval(object):
    schema = {'type': 'boolean'}

    @staticmethod
    def _item_query(entry, task, session):
        return session.query(PendingEntry) \
            .filter(PendingEntry.task_name == task.name) \
            .filter(PendingEntry.title == entry['title']) \
            .filter(PendingEntry.url == entry['url']) \
            .first()

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not config:
            return

        approved_entries = []
        with Session() as session:
            for entry in task.entries:
                # Cache all new task entries
                if not self._item_query(entry, task, session):
                    log.verbose('creating new pending entry %s', entry)
                    session.add(PendingEntry(task_name=task.name, entry=entry))
                    entry.reject('new unapproved entry, caching and waiting for approval')

            # Pass all entries marked as approved
            for approved_entry in session.query(PendingEntry) \
                    .filter(PendingEntry.task_name == task.name) \
                    .filter(PendingEntry.approved == True) \
                    .all():
                e = approved_entry.entry
                e['approved'] = True
                approved_entries.append(e)

        return approved_entries

    def on_task_learn(self, task, config):
        if not config:
            return
        with Session() as session:
            # Delete all entries that have passed the pending phase
            for entry in task.accepted:
                if entry.get('approved', False) is True:
                    db_entry = self._item_query(entry, task, session)
                    if db_entry and db_entry.approved:
                        log.debug('deleting approved entry %s', db_entry)
                        session.delete(db_entry)


@event('plugin.register')
def register_plugin():
    plugin.register(PendingApproval, 'pending_approval', api_ver=2)


def list_pending_entries(session, task_name=None, approved=None, start=None, stop=None, order_by='added',
                         descending=True):
    log.debug('querying pending entries')
    query = session.query(PendingEntry)
    if task_name:
        query = query.filter(PendingEntry.task_name == task_name)
    if approved is not None:
        query = query.filter(PendingEntry.approved == approved)
    if descending:
        query = query.order_by(getattr(PendingEntry, order_by).desc())
    else:
        query = query.order_by(getattr(PendingEntry, order_by))
    return query.slice(start, stop).all()
