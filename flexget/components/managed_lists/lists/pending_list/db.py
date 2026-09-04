from __future__ import annotations

from datetime import datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import DynamicMapped, Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import and_
from sqlalchemy.sql.schema import ForeignKey

from flexget import db_schema
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym, with_session
from flexget.utils.sqlalchemy_utils import table_schema

plugin_name = 'pending_list'
logger = logger.bind(name=plugin_name)
Base = versioned_base(plugin_name, 1)


@db_schema.upgrade(plugin_name)
def upgrade(ver, session):
    if ver is None:
        ver = 0
    if ver == 0:
        table = table_schema('wait_list_entries', session)
        for row in session.execute(select(table.c.id, table.c.json)):
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
        ver = 1
    return ver


class PendingListList(Base):
    __tablename__ = 'pending_list_lists'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(unique=True)
    added: Mapped[datetime | None] = mapped_column(default=datetime.now)
    entries: DynamicMapped[PendingListEntry] = relationship(
        back_populates='list_', cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


class PendingListEntry(Base):
    __tablename__ = 'wait_list_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey(PendingListList.id))
    list_: Mapped[PendingListList] = relationship(back_populates='entries')
    added: Mapped[datetime | None] = mapped_column(default=datetime.now)
    title: Mapped[str | None]
    original_url: Mapped[str | None]
    _json: Mapped[str | None] = mapped_column('json')
    entry = entry_synonym('_json')
    approved: Mapped[bool | None]

    def __init__(self, entry, pending_list_id):
        self.title = entry['title']
        self.original_url = entry.get('original_url') or entry['url']
        self.entry = entry
        self.list_id = pending_list_id
        self.approved = False

    def __repr__(self):
        return f'<PendingListEntry,title={self.title},original_url={self.original_url},approved={self.approved}>'

    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'added_on': self.added,
            'title': self.title,
            'original_url': self.original_url,
            'entry': json.coerce(self.entry),
            'approved': self.approved,
        }


@with_session
def get_pending_lists(name=None, session=None):
    logger.debug('retrieving pending lists')
    query = session.query(PendingListList)
    if name:
        logger.debug('searching for pending lists with name {}', name)
        query = query.filter(PendingListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    logger.debug('returning pending list with name {}', name)
    return (
        session
        .query(PendingListList)
        .filter(func.lower(PendingListList.name) == name.lower())
        .one()
    )


@with_session
def get_list_by_id(list_id, session=None):
    logger.debug('returning pending list with id {}', list_id)
    return session.query(PendingListList).filter(PendingListList.id == list_id).one()


@with_session
def delete_list_by_id(list_id, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        logger.debug('deleting pending list with id {}', list_id)
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
    entry_ids=None,
    session=None,
):
    logger.debug('querying entries from pending list with id {}', list_id)
    query = session.query(PendingListEntry).filter(PendingListEntry.list_id == list_id)
    if filter:
        query = query.filter(func.lower(PendingListEntry.title).contains(filter.lower()))
    if approved:
        query = query.filter(PendingListEntry.approved is approved)
    if entry_ids:
        query = query.filter(PendingListEntry.id.in_(entry_ids))
    if descending:
        query = query.order_by(getattr(PendingListEntry, order_by).desc())
    else:
        query = query.order_by(getattr(PendingListEntry, order_by))
    return query.slice(start, stop).all()


@with_session
def get_entry_by_title(list_id, title, session=None):
    entry_list = get_list_by_id(list_id=list_id, session=session)
    if entry_list:
        logger.debug('fetching entry with title `{}` from list id {}', title, list_id)
        return (
            session
            .query(PendingListEntry)
            .filter(and_(PendingListEntry.title == title, PendingListEntry.list_id == list_id))
            .first()
        )
    return None


@with_session
def get_entry_by_id(list_id, entry_id, session=None):
    logger.debug('fetching entry with id {} from list id {}', entry_id, list_id)
    return (
        session
        .query(PendingListEntry)
        .filter(and_(PendingListEntry.id == entry_id, PendingListEntry.list_id == list_id))
        .one()
    )
