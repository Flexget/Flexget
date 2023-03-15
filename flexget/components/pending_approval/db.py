from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Unicode, select

from flexget import db_schema
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym
from flexget.utils.sqlalchemy_utils import table_schema

logger = logger.bind(name='pending_approval')
Base = db_schema.versioned_base('pending_approval', 1)


@db_schema.upgrade('pending_approval')
def upgrade(ver, session):
    if ver == 0:
        table = table_schema('pending_entries', session)
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

        ver = 1
    return ver


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
        logger.info('Purged {} pending entries older than 1 year', deleted)


def list_pending_entries(
    session, task_name=None, approved=None, start=None, stop=None, sort_by='added', descending=True
):
    logger.debug('querying pending entries')
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
