from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget.manager import Session
from sqlalchemy import Column, String, Unicode, Boolean, Integer
from flexget import db_schema, plugin
from flexget.event import event

log = logging.getLogger('pending_approval')
Base = db_schema.versioned_base('pending_approval', 0)


class PendingEntry(Base):
    __tablename__ = 'pending_entries'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_name = Column(Unicode)
    title = Column(Unicode)
    url = Column(String)
    approved = Column(Boolean)

    def __init__(self, task_name, title, url):
        self.task_name = task_name
        self.title = title
        self.url = url
        self.approved = False

    def __repr__(self):
        return '<PendingEntry(task_name={},title={},url={},approved={})>' \
            .format(self.task_name, self.title, self.url, self.approved)


class PendingApproval(object):
    schema = {'type': 'boolean'}

    @staticmethod
    def _item_query(entry, task, session):
        db_entry = session.query(PendingEntry) \
            .filter(PendingEntry.task_name == task.name) \
            .filter(PendingEntry.title == entry['title']) \
            .filter(PendingEntry.url == entry['url']) \
            .first()
        return db_entry

    @plugin.priority(0)
    def on_task_filter(self, task, config):
        if not config:
            return

        for entry in task.entries:
            with Session() as session:
                db_entry = self._item_query(entry, task, session)
                if not db_entry:
                    db_entry = PendingEntry(task_name=task.name, title=entry['title'], url=entry['url'])
                    log.debug('creating new pending entry %s', db_entry)
                session.merge(db_entry)

                if db_entry.approved is True:
                    entry.accept('approval was set to True')

    def on_task_learn(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            with Session() as session:
                db_entry = self._item_query(entry, task, session)
                if db_entry:
                    log.debug('deleting approved entry %s', db_entry)
                    session.delete(db_entry)


@event('plugin.register')
def register_plugin():
    plugin.register(PendingApproval, 'pending_approval', api_ver=2)
