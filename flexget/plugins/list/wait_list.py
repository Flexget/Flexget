from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, DateTime, or_, func, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_
from sqlalchemy.sql.schema import ForeignKey

from flexget import plugin, db_schema
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import entry_synonym, with_session

log = logging.getLogger('wait_list')
Base = versioned_base('wait_list', 0)


@db_schema.upgrade('wait_list')
def upgrade(ver, session):
    ver = 0
    return ver


class WaitListList(Base):
    __tablename__ = 'wait_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    entries = relationship('WaitListEntry', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class WaitListEntry(Base):
    __tablename__ = 'wait_list_entries'
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey(WaitListList.id), nullable=False)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    original_url = Column(Unicode)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')
    approved = Column(Boolean)

    def __init__(self, entry, wait_list_id):
        self.title = entry['title']
        self.original_url = entry.get('original_url') or entry['url']
        self.entry = entry
        self.list_id = wait_list_id
        self.approved = False

    def __repr__(self):
        return '<WaitListEntry,title=%s,original_url=%s,approved=%s>' % (self.title, self.original_url, self.approved)

    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'added_on': self.added,
            'title': self.title,
            'original_url': self.original_url,
            'entry': dict(self.entry),
            'approved': self.approved
        }


class WaitListSet(MutableSet):
    def _db_list(self, session):
        return session.query(WaitListList).filter(WaitListList.name == self.config).first()

    def __init__(self, config):
        self.config = config
        with Session() as session:
            if not self._db_list(session):
                session.add(WaitListList(name=self.config))

    def _entry_query(self, session, entry, approved=None):
        query = session.query(WaitListEntry).filter(WaitListEntry.list_id == self._db_list(session).id). \
            filter(or_(WaitListEntry.title == entry['title'],
                       and_(WaitListEntry.original_url, WaitListEntry.original_url == entry['original_url'])))
        if approved:
            query = query.filter(WaitListEntry.approved == True)
        return query.first()

    def __iter__(self):
        with Session() as session:
            for e in self._db_list(session).entries.filter(WaitListEntry.approved == True).order_by(
                    WaitListEntry.added.desc()).all():
                log.debug('returning %s', e.entry)
                yield e.entry

    def __contains__(self, entry):
        with Session() as session:
            return self._entry_query(session, entry) is not None

    def __len__(self):
        with Session() as session:
            return self._db_list(session).entries.count()

    def discard(self, entry):
        with Session() as session:
            db_entry = self._entry_query(session=session, entry=entry)
            if db_entry:
                log.debug('deleting wait entry %s', db_entry)
                session.delete(db_entry)

    def add(self, entry):
        # Evaluate all lazy fields so that no db access occurs during our db session
        entry.values()

        with Session() as session:
            stored_entry = self._entry_query(session, entry)
            if stored_entry:
                # Refresh all the fields if we already have this entry
                log.debug('refreshing wait entry %s', entry)
                stored_entry.entry = entry
            else:
                log.debug('adding wait entry %s to list %s', entry, self._db_list(session).name)
                stored_entry = WaitListEntry(entry=entry, wait_list_id=self._db_list(session).id)
            session.add(stored_entry)

    def __ior__(self, other):
        # Optimization to only open one session when adding multiple items
        # Make sure lazy lookups are done before opening our session to prevent db locks
        for value in other:
            value.values()
        for value in other:
            self.add(value)
        return self

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        return set(it)

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    def get(self, entry):
        with Session() as session:
            match = self._entry_query(session=session, entry=entry, approved=True)
            return Entry(match.entry) if match else None


class WaitList(object):
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return WaitListSet(config)

    def on_task_input(self, task, config):
        return list(WaitListSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(WaitList, 'wait_list', api_ver=2, groups=['list'])


@with_session
def get_wait_lists(name=None, session=None):
    log.debug('retrieving wait lists')
    query = session.query(WaitListList)
    if name:
        log.debug('searching for entry lists with name %s', name)
        query = query.filter(WaitListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    log.debug('returning wait list with name %s', name)
    return session.query(WaitListList).filter(func.lower(WaitListList.name) == name.lower()).one()


@with_session
def get_list_by_id(list_id, session=None):
    log.debug('fetching wait list with id %d', list_id)
    return session.query(WaitListList).filter(WaitListList.id == list_id).one()


@with_session
def delete_list_by_id(list_id, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        log.debug('deleting entry list with id %d', list_id)
        session.delete(entry_list)


@with_session
def get_wait_entries_by_list_id(list_id, start=None, stop=None, order_by='title', descending=False, approved=False,
                                session=None):
    log.debug('querying entries from entry list with id %d', list_id)
    query = session.query(WaitListEntry).filter(WaitListEntry.list_id == list_id)
    if approved:
        query = query.filter(WaitListEntry.approved is approved)
    if descending:
        query = query.order_by(getattr(WaitListEntry, order_by).desc())
    else:
        query = query.order_by(getattr(WaitListEntry, order_by))
    return query.slice(start, stop).all()


@with_session
def get_wait_entry_by_title(list_id, title, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        return session.query(WaitListEntry).filter(and_(
            WaitListEntry.title == title, WaitListEntry.list_id == list_id)).first()


@with_session
def get_wait_entry_by_id(list_id, entry_id, session=None):
    log.debug('fetching wait entry with id %d from list id %d', entry_id, list_id)
    return session.query(WaitListEntry).filter(
        and_(WaitListEntry.id == entry_id, WaitListEntry.list_id == list_id)).one()
