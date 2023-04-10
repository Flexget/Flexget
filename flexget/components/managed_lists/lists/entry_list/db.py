import pickle
from collections.abc import MutableSet
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, func, or_, select
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_

from flexget import db_schema
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.manager import Session
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym, with_session
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema

logger = logger.bind(name='entry_list.db')
Base = versioned_base('entry_list', 2)


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
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except KeyError as e:
                logger.error('Unable error upgrading entry_list pickle object due to {}', str(e))

        ver = 1
    if ver == 1:
        table = table_schema('entry_list_entries', session)
        for row in session.execute(select([table.c.id, table.c.json])):
            if not row['json']:
                # Seems there could be invalid data somehow. See #2590
                continue
            data = json.loads(row['json'], decode_datetime=True)
            # If title looked like a date, make sure it's a string
            title = str(data.pop('title'))
            e = Entry(title=title, **data)
            session.execute(
                table.update().where(table.c.id == row['id']).values(json=serialization.dumps(e))
            )
        ver = 2
    return ver


class EntryListList(Base):
    __tablename__ = 'entry_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    entries = relationship(
        'EntryListEntry', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic'
    )

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


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
        self.original_url = entry.get('original_url') or entry['url']
        self.entry = entry
        self.list_id = entry_list_id

    def __repr__(self):
        return f'<EntryListEntry,title={self.title},original_url={self.original_url}>'

    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'added_on': self.added,
            'title': self.title,
            'original_url': self.original_url,
            'entry': json.coerce(self.entry),
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
        db_entry = (
            session.query(EntryListEntry)
            .filter(
                and_(
                    EntryListEntry.list_id == self._db_list(session).id,
                    or_(
                        EntryListEntry.title == entry['title'],
                        and_(
                            EntryListEntry.original_url,
                            EntryListEntry.original_url == entry['original_url'],
                        ),
                    ),
                )
            )
            .first()
        )

        return db_entry

    def __iter__(self):
        with Session() as session:
            for e in self._db_list(session).entries.order_by(EntryListEntry.added.desc()).all():
                logger.debug('returning {}', e.entry)
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
                logger.debug('deleting entry {}', db_entry)
                session.delete(db_entry)

    def add(self, entry):
        with Session() as session:
            stored_entry = self._entry_query(session, entry)
            if stored_entry:
                # Refresh all the fields if we already have this entry
                logger.debug('refreshing entry {}', entry)
                stored_entry.entry = entry
            else:
                logger.debug('adding entry {} to list {}', entry, self._db_list(session).name)
                stored_entry = EntryListEntry(entry=entry, entry_list_id=self._db_list(session).id)
            session.add(stored_entry)

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @property
    def online(self):
        """Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    def get(self, entry):
        with Session() as session:
            match = self._entry_query(session=session, entry=entry)
            return Entry(match.entry) if match else None


@with_session
def get_entry_lists(name=None, session=None):
    logger.debug('retrieving entry lists')
    query = session.query(EntryListList)
    if name:
        logger.debug('searching for entry lists with name {}', name)
        query = query.filter(EntryListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    logger.debug('returning entry list with name {}', name)
    return (
        session.query(EntryListList).filter(func.lower(EntryListList.name) == name.lower()).one()
    )


@with_session
def get_list_by_id(list_id, session=None):
    logger.debug('fetching entry list with id {}', list_id)
    return session.query(EntryListList).filter(EntryListList.id == list_id).one()


@with_session
def delete_list_by_id(list_id, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        logger.debug('deleting entry list with id {}', list_id)
        session.delete(entry_list)


@with_session
def get_entries_by_list_id(
    list_id,
    start=None,
    stop=None,
    order_by='title',
    descending=False,
    entry_ids=None,
    session=None,
):
    logger.debug('querying entries from entry list with id {}', list_id)
    query = session.query(EntryListEntry).filter(EntryListEntry.list_id == list_id)
    if entry_ids:
        query = query.filter(EntryListEntry.id.in_(entry_ids))
    if descending:
        query = query.order_by(getattr(EntryListEntry, order_by).desc())
    else:
        query = query.order_by(getattr(EntryListEntry, order_by))
    return query.slice(start, stop).all()


@with_session
def get_entry_by_title(list_id, title, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        return (
            session.query(EntryListEntry)
            .filter(and_(EntryListEntry.title == title, EntryListEntry.list_id == list_id))
            .first()
        )


@with_session
def get_entry_by_id(list_id, entry_id, session=None):
    logger.debug('fetching entry with id {} from list id {}', entry_id, list_id)
    return (
        session.query(EntryListEntry)
        .filter(and_(EntryListEntry.id == entry_id, EntryListEntry.list_id == list_id))
        .one()
    )
