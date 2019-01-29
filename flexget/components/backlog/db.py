import logging
import pickle
from datetime import datetime

from sqlalchemy import Index, Unicode, select, Column, Integer, String, DateTime

from flexget import db_schema
from flexget.utils import json
from flexget.utils.database import entry_synonym, with_session
from flexget.utils.sqlalchemy_utils import table_schema, table_add_column

log = logging.getLogger('backlog.db')
Base = db_schema.versioned_base('backlog', 2)


class BacklogEntry(Base):
    __tablename__ = 'backlog'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    title = Column(String)
    expire = Column(DateTime)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')

    def __repr__(self):
        return '<BacklogEntry(title=%s)>' % (self.title)


Index('ix_backlog_feed_expire', BacklogEntry.task, BacklogEntry.expire)


@db_schema.upgrade('backlog')
def upgrade(ver, session):
    if ver is None:
        # Make sure there is no data we can't load in the backlog table
        backlog_table = table_schema('backlog', session)
        try:
            for item in session.query('entry').select_from(backlog_table).all():
                pickle.loads(item.entry)
        except (ImportError, TypeError):
            # If there were problems, we can drop the data.
            log.info('Backlog table contains unloadable data, clearing old data.')
            session.execute(backlog_table.delete())
        ver = 0
    if ver == 0:
        backlog_table = table_schema('backlog', session)
        log.info('Creating index on backlog table.')
        Index('ix_backlog_feed_expire', backlog_table.c.feed, backlog_table.c.expire).create(
            bind=session.bind
        )
        ver = 1
    if ver == 1:
        table = table_schema('backlog', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('backlog', session)
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except KeyError as e:
                log.error('Unable error upgrading backlog pickle object due to %s' % str(e))

        ver = 2
    return ver


@with_session
def get_entries(task=None, session=None):
    query = session.query(BacklogEntry)
    if task:
        query = query.filter(BacklogEntry.task == task)
    return query.all()


@with_session
def clear_entries(task=None, all=False, session=None):
    """
    Clear entries from backlog.

    :param task: If given, only entries from specified task will be cleared.
    :param all: If True, all entries will be cleared, otherwise only expired entries will be cleared.
    :returns: Number of entries cleared from backlog.
    """
    query = session.query(BacklogEntry)
    if task:
        query = query.filter(BacklogEntry.task == task)
    if not all:
        query = query.filter(BacklogEntry.expire < datetime.now())
    return query.delete()
