from __future__ import unicode_literals, division, absolute_import

import logging
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, PickleType, Integer, DateTime, or_
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.database import safe_pickle_synonym, with_session

log = logging.getLogger('entry_list')
Base = versioned_base('entry_list', 0)


class StoredEntry(Base):
    __tablename__ = 'entry_list'
    id = Column(Integer, primary_key=True)
    list = Column(Unicode, index=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    original_url = Column(Unicode)
    _entry = Column('entry', PickleType)
    entry = safe_pickle_synonym('_entry')

    def __init__(self, list, entry):
        self.list = list
        self.title = entry['title']
        self.original_url = entry['original_url']
        self.entry = entry

    def __repr__(self):
        return '<StoredEntry,title=%s,original_url=%s>' % (self.title, self.original_url)


class DBEntrySet(MutableSet):
    def __init__(self, config):
        self.config = config

    def _query(self, session):
        return session.query(StoredEntry).filter(StoredEntry.list == self.config)

    def _entry_query(self, session, entry):
        query = self._query(session)
        db_entry = query.filter(or_(
            StoredEntry.title == entry['title'], and_(
                StoredEntry.original_url,
                StoredEntry.original_url == entry['original_url']))).first()
        if db_entry:
            return db_entry

    @with_session
    def __iter__(self, session=None):
        return (Entry(e.entry) for e in self._query(session).order_by(StoredEntry.added.desc()).all())

    @with_session
    def __contains__(self, entry, session=None):
        return self._entry_query(session, entry) is not None

    @with_session
    def __len__(self, session=None):
        return self._query(session).count()

    @with_session
    def discard(self, entry, session=None):
        db_entry = self._entry_query(session=session, entry=entry)
        if db_entry:
            log.debug('deleting entry %s', db_entry)
            session.delete(db_entry)

    @with_session
    def add(self, entry, session=None):
        stored_entry = self._entry_query(session, entry)
        if stored_entry:
            # Refresh all the fields if we already have this entry
            log.debug('refreshing entry %s', entry)
            stored_entry.entry = entry
        else:
            log.debug('adding entry %s', entry)
            session.add(StoredEntry(list=self.config, entry=entry))

    @with_session
    def __ior__(self, other, session=None):
        # Optimization to only open one session when adding multiple items
        for value in other:
            self.add(value, session=session)
        return self

    update = __ior__


class EntryList(object):
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return DBEntrySet(config)

    def on_task_input(self, task, config):
        return list(DBEntrySet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(EntryList, 'entry_list', api_ver=2, groups=['list'])
