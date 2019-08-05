from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, DateTime, func, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_
from sqlalchemy.sql.schema import ForeignKey

from flexget import db_schema
from flexget.db_schema import versioned_base
from flexget.utils.database import entry_synonym, with_session

plugin_name = 'pending_list'
log = logging.getLogger(plugin_name)
Base = versioned_base(plugin_name, 0)


@db_schema.upgrade(plugin_name)
def upgrade(ver, session):
    ver = 0
    return ver


class PendingListList(Base):
    __tablename__ = 'pending_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    entries = relationship(
        'PendingListEntry', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic'
    )

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


class PendingListEntry(Base):
    __tablename__ = 'wait_list_entries'
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey(PendingListList.id), nullable=False)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    original_url = Column(Unicode)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')
    approved = Column(Boolean)

    def __init__(self, entry, pending_list_id):
        self.title = entry['title']
        self.original_url = entry.get('original_url') or entry['url']
        self.entry = entry
        self.list_id = pending_list_id
        self.approved = False

    def __repr__(self):
        return '<PendingListEntry,title=%s,original_url=%s,approved=%s>' % (
            self.title,
            self.original_url,
            self.approved,
        )

    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'added_on': self.added,
            'title': self.title,
            'original_url': self.original_url,
            'entry': dict(self.entry),
            'approved': self.approved,
        }


@with_session
def get_pending_lists(name=None, session=None):
    log.debug('retrieving pending lists')
    query = session.query(PendingListList)
    if name:
        log.debug('searching for pending lists with name %s', name)
        query = query.filter(PendingListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    log.debug('returning pending list with name %s', name)
    return (
        session.query(PendingListList)
        .filter(func.lower(PendingListList.name) == name.lower())
        .one()
    )


@with_session
def get_list_by_id(list_id, session=None):
    log.debug('returning pending list with id %d', list_id)
    return session.query(PendingListList).filter(PendingListList.id == list_id).one()


@with_session
def delete_list_by_id(list_id, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        log.debug('deleting pending list with id %d', list_id)
        session.delete(entry_list)


@with_session
def get_entries_by_list_id(
    list_id,
    start=None,
    stop=None,
    order_by='title',
    descending=False,
    approved=False,
    filter=None,
    session=None,
):
    log.debug('querying entries from pending list with id %d', list_id)
    query = session.query(PendingListEntry).filter(PendingListEntry.list_id == list_id)
    if filter:
        query = query.filter(func.lower(PendingListEntry.title).contains(filter.lower()))
    if approved:
        query = query.filter(PendingListEntry.approved is approved)
    if descending:
        query = query.order_by(getattr(PendingListEntry, order_by).desc())
    else:
        query = query.order_by(getattr(PendingListEntry, order_by))
    return query.slice(start, stop).all()


@with_session
def get_entry_by_title(list_id, title, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        log.debug('fetching entry with title `%s` from list id %d', title, list_id)
        return (
            session.query(PendingListEntry)
            .filter(and_(PendingListEntry.title == title, PendingListEntry.list_id == list_id))
            .first()
        )


@with_session
def get_entry_by_id(list_id, entry_id, session=None):
    log.debug('fetching entry with id %d from list id %d', entry_id, list_id)
    return (
        session.query(PendingListEntry)
        .filter(and_(PendingListEntry.id == entry_id, PendingListEntry.list_id == list_id))
        .one()
    )
