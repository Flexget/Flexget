from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None]

    entries: Mapped[list[RememberEntry]] = relationship(
        back_populates='task', cascade='all, delete-orphan'
    )


class RememberEntry(Base):
    __tablename__ = 'remember_rejected_entry'

    id: Mapped[int] = mapped_column(primary_key=True)
    added: Mapped[datetime | None] = mapped_column(default=datetime.now)
    expires: Mapped[datetime | None]
    title: Mapped[str | None]
    url: Mapped[str | None]
    rejected_by: Mapped[str | None]
    reason: Mapped[str | None]

    task_id: Mapped[int] = mapped_column('feed_id', ForeignKey('remember_rejected_feeds.id'))
    task: Mapped[RememberTask] = relationship(back_populates='entries')


Index('remember_feed_title_url', RememberEntry.task_id, RememberEntry.title, RememberEntry.url)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Remove entries older than 30 days
    result = (
        session
        .query(RememberEntry)
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
