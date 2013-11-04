from __future__ import unicode_literals, division, absolute_import
import logging
import pickle
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, PickleType, Index

from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.database import safe_pickle_synonym
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('backlog')
Base = db_schema.versioned_base('backlog', 1)


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
        Index('ix_backlog_feed_expire', backlog_table.c.feed, backlog_table.c.expire).create(bind=session.bind)
        ver = 1
    return ver


class BacklogEntry(Base):

    __tablename__ = 'backlog'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    title = Column(String)
    expire = Column(DateTime)
    _entry = Column('entry', PickleType)
    entry = safe_pickle_synonym('_entry')

    def __repr__(self):
        return '<BacklogEntry(title=%s)>' % (self.title)

Index('ix_backlog_feed_expire', BacklogEntry.task, BacklogEntry.expire)


class InputBacklog(object):
    """
    Keeps task history for given amount of time.

    Example::

      backlog: 4 days

    Rarely useful for end users, mainly used by other plugins.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('interval')

    @plugin.priority(-255)
    def on_task_input(self, task, config):
        # Get a list of entries to inject
        injections = self.get_injections(task)
        # Take a snapshot of the entries' states after the input event in case we have to store them to backlog
        for entry in task.entries + injections:
            entry.take_snapshot('after_input')
        if config:
            # If backlog is manually enabled for this task, learn the entries.
            self.learn_backlog(task, config)
        # Return the entries from backlog that are not already in the task
        return injections

    def on_task_abort(self, task, config):
        """Remember all entries until next execution when task gets aborted."""
        if task.entries:
            log.debug('Remembering all entries to backlog because of task abort.')
            self.learn_backlog(task)

    def add_backlog(self, task, entry, amount=''):
        """Add single entry to task backlog

        If :amount: is not specified, entry will only be injected on next execution."""
        snapshot = entry.snapshots.get('after_input')
        if not snapshot:
            if task.current_phase != 'input':
                # Not having a snapshot is normal during input phase, don't display a warning
                log.warning('No input snapshot available for `%s`, using current state' % entry['title'])
            snapshot = entry
        expire_time = datetime.now() + parse_timedelta(amount)
        backlog_entry = task.session.query(BacklogEntry).filter(BacklogEntry.title == entry['title']).\
            filter(BacklogEntry.task == task.name).first()
        if backlog_entry:
            # If there is already a backlog entry for this, update the expiry time if necessary.
            if backlog_entry.expire < expire_time:
                log.debug('Updating expiry time for %s' % entry['title'])
                backlog_entry.expire = expire_time
        else:
            log.debug('Saving %s' % entry['title'])
            backlog_entry = BacklogEntry()
            backlog_entry.title = entry['title']
            backlog_entry.entry = snapshot
            backlog_entry.task = task.name
            backlog_entry.expire = expire_time
            task.session.add(backlog_entry)

    def learn_backlog(self, task, amount=''):
        """Learn current entries into backlog. All task inputs must have been executed."""
        for entry in task.entries:
            self.add_backlog(task, entry, amount)

    def get_injections(self, task):
        """Insert missing entries from backlog."""
        entries = []
        task_backlog = task.session.query(BacklogEntry).filter(BacklogEntry.task == task.name)
        for backlog_entry in task_backlog.all():
            entry = Entry(backlog_entry.entry)

            # this is already in the task
            if task.find_entry(title=entry['title'], url=entry['url']):
                continue
            log.debug('Restoring %s' % entry['title'])
            entries.append(entry)
        if entries:
            log.verbose('Added %s entries from backlog' % len(entries))

        # purge expired
        for backlog_entry in task_backlog.filter(datetime.now() > BacklogEntry.expire).all():
            log.debug('Purging %s' % backlog_entry.title)
            task.session.delete(backlog_entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputBacklog, 'backlog', builtin=True, api_ver=2)
