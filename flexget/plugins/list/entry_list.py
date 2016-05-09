from __future__ import unicode_literals, division, absolute_import

import logging
import pickle
from collections import MutableSet
from datetime import datetime

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from sqlalchemy import Column, Unicode, select, Integer, DateTime, or_, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_
from sqlalchemy.sql.schema import ForeignKey

from flexget import plugin, db_schema
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils import json
from flexget.utils.database import entry_synonym, with_session
from flexget.utils.sqlalchemy_utils import table_schema, table_add_column

log = logging.getLogger('entry_list')
Base = versioned_base('entry_list', 1)


@db_schema.upgrade('entry_list')
def upgrade(ver, session):
    if None is ver:
        ver = 0
    if ver == 0:
        table = table_schema('entry_list_entries', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('entry_list_entries', session)
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(table.update().where(table.c.id == row['id']).values(
                    json=json.dumps(p, encode_datetime=True)))
            except KeyError as e:
                log.error('Unable error upgrading entry_list pickle object due to %s' % str(e))

        ver = 1
    return ver


class EntryListList(Base):
    __tablename__ = 'entry_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    entries = relationship('EntryListEntry', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class EntryListEntry(Base):
    __tablename__ = 'entry_list_entries'
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey(EntryListList.id), nullable=False)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    original_url = Column(Unicode)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')

    def __init__(self, entry, entry_list_id):
        self.title = entry['title']
        self.original_url = entry['original_url']
        self.entry = entry
        self.list_id = entry_list_id

    def __repr__(self):
        return '<EntryListEntry,title=%s,original_url=%s>' % (self.title, self.original_url)

    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'added_on': self.added,
            'title': self.title,
            'original_url': self.original_url,
            'entry': dict(self.entry)
        }


class DBEntrySet(MutableSet):
    def _db_list(self, session):
        return session.query(EntryListList).filter(EntryListList.name == self.config).first()

    def __init__(self, config):
        self.config = config
        with Session() as session:
            if not self._db_list(session):
                session.add(EntryListList(name=self.config))

    def _entry_query(self, session, entry):
        db_entry = session.query(EntryListEntry).filter(and_(
            EntryListEntry.list_id == self._db_list(session).id,
            or_(
                EntryListEntry.title == entry['title'], and_(
                    EntryListEntry.original_url,
                    EntryListEntry.original_url == entry[
                        'original_url'])))).first()

        return db_entry

    @with_session
    def __iter__(self, session=None):
        return (Entry(e.entry) for e in
                self._db_list(session).entries.order_by(EntryListEntry.added.desc()).all())

    @with_session
    def __contains__(self, entry, session=None):
        return self._entry_query(session, entry) is not None

    @with_session
    def __len__(self, session=None):
        return self._db_list(session).entries.count()

    @with_session
    def discard(self, entry, session=None):
        db_entry = self._entry_query(session=session, entry=entry)
        if db_entry:
            log.debug('deleting entry %s', db_entry)
            session.delete(db_entry)

    @with_session
    def add(self, entry, session=None):
        # Evaluate all lazy fields so that no db access occurs during our db session
        entry.values()
        stored_entry = self._entry_query(session, entry)
        if stored_entry:
            # Refresh all the fields if we already have this entry
            log.debug('refreshing entry %s', entry)
            stored_entry.entry = entry
        else:
            log.debug('adding entry %s to list %s', entry, self._db_list(session).name)
            stored_entry = EntryListEntry(entry=entry, entry_list_id=self._db_list(session).id)
        session.add(stored_entry)

    def __ior__(self, other):
        # Optimization to only open one session when adding multiple items
        # Make sure lazy lookups are done before opening our session to prevent db locks
        for value in other:
            value.values()
        with Session() as session:
            for value in other:
                self.add(value, session=session)
        return self

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    @with_session
    def get(self, entry, session=None):
        match = self._entry_query(session=session, entry=entry)
        return Entry(match.entry) if match else None


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


@with_session
def get_entry_lists(name=None, session=None):
    log.debug('retrieving entry lists')
    query = session.query(EntryListList)
    if name:
        log.debug('searching for entry lists with name %s', name)
        query = query.filter(EntryListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    log.debug('returning entry list with name %s', name)
    return session.query(EntryListList).filter(func.lower(EntryListList.name) == name.lower()).one()


@with_session
def get_list_by_id(list_id, session=None):
    log.debug('fetching entry list with id %d', list_id)
    return session.query(EntryListList).filter(EntryListList.id == list_id).one()


@with_session
def delete_list_by_id(list_id, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        log.debug('deleting entry list with id %d', list_id)
        session.delete(entry_list)


@with_session
def get_entries_by_list_id(list_id, count=False, start=None, stop=None, order_by='title', descending=False,
                           session=None):
    log.debug('querying entries from entry list with id %d', list_id)
    query = session.query(EntryListEntry).join(EntryListList).filter(EntryListList.id == list_id)
    if count:
        return query.count()
    query = query.slice(start, stop).from_self()
    if descending:
        query = query.order_by(getattr(EntryListEntry, order_by).desc())
    else:
        query = query.order_by(getattr(EntryListEntry, order_by))
    return query.all()


@with_session
def get_entry_by_title(list_id, title, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        return session.query(EntryListEntry).filter(and_(
            EntryListEntry.title == title, EntryListEntry.list_id == list_id)).first()


@with_session
def get_entry_by_id(list_id, entry_id, session=None):
    log.debug('fetching entry with id %d from list id %d', entry_id, list_id)
    return session.query(EntryListEntry).filter(
        and_(EntryListEntry.id == entry_id, EntryListEntry.list_id == list_id)).one()
