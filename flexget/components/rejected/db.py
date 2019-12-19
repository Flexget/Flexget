from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Unicode
from sqlalchemy.orm import relation

from flexget import db_schema
from flexget.event import event
from flexget.utils.sqlalchemy_utils import table_add_column, table_columns

logger = logger.bind(name='remember_rej')
Base = db_schema.versioned_base('remember_rejected', 3)


@db_schema.upgrade('remember_rejected')
def upgrade(ver, session):
    if ver is None:
        columns = table_columns('remember_rejected_entry', session)
        if 'uid' in columns:
            raise db_schema.UpgradeImpossible
        ver = 0
    if ver == 0:
        logger.info('Adding reason column to remember_rejected_entry table.')
        table_add_column('remember_rejected_entry', 'reason', String, session)
        ver = 1
    if ver == 1:
        logger.info('Adding `added` column to remember_rejected_entry table.')
        table_add_column(
            'remember_rejected_entry', 'added', DateTime, session, default=datetime.now
        )
        ver = 2
    if ver == 2:
        logger.info('Adding expires column to remember_rejected_entry table.')
        table_add_column('remember_rejected_entry', 'expires', DateTime, session)
        ver = 3
    return ver


class RememberTask(Base):
    __tablename__ = 'remember_rejected_feeds'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    entries = relation('RememberEntry', backref='task', cascade='all, delete, delete-orphan')


class RememberEntry(Base):
    __tablename__ = 'remember_rejected_entry'

    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    expires = Column(DateTime)
    title = Column(Unicode)
    url = Column(String)
    rejected_by = Column(String)
    reason = Column(String)

    task_id = Column('feed_id', Integer, ForeignKey('remember_rejected_feeds.id'), nullable=False)


Index('remember_feed_title_url', RememberEntry.task_id, RememberEntry.title, RememberEntry.url)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Remove entries older than 30 days
    result = (
        session.query(RememberEntry)
        .filter(RememberEntry.added < datetime.now() - timedelta(days=30))
        .delete()
    )
    if result:
        logger.verbose('Removed {} entries from remember rejected table.', result)


def get_rejected(session, count=None, start=None, stop=None, sort_by=None, descending=None):
    query = session.query(RememberEntry)
    if count:
        return query.count()
    if descending:
        query = query.order_by(getattr(RememberEntry, sort_by).desc())
    else:
        query = query.order_by(getattr(RememberEntry, sort_by))
    return query.slice(start, stop).all()
