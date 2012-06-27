import logging
import pickle
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, PickleType, Index
from flexget import schema
from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugin import register_plugin, priority
from flexget.utils.database import safe_pickle_synonym
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('backlog')
Base = schema.versioned_base('backlog', 1)


@schema.upgrade('backlog')
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
    feed = Column(String)
    title = Column(String)
    expire = Column(DateTime)
    _entry = Column('entry', PickleType(mutable=False))
    entry = safe_pickle_synonym('_entry')

    def __repr__(self):
        return '<BacklogEntry(title=%s)>' % (self.title)

Index('ix_backlog_feed_expire', BacklogEntry.feed, BacklogEntry.expire)


class InputBacklog(object):
    """
    Keeps feed history for given amount of time.

    Example:

    backlog: 4 days

    Rarely useful for end users, mainly used by other plugins.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('interval')

    @priority(-255)
    def on_feed_input(self, feed, config):
        # Get a list of entries to inject
        injections = self.get_injections(feed)
        # Take a snapshot of the entries' states after the input event in case we have to store them to backlog
        for entry in feed.entries + injections:
            entry.take_snapshot('after_input')
        if config:
            # If backlog is manually enabled for this feed, learn the entries.
            self.learn_backlog(feed, config)
        # Return the entries from backlog that are not already in the feed
        return injections

    def on_feed_abort(self, feed, config):
        """Remember all entries until next execution when feed gets aborted."""
        if feed.entries:
            log.debug('Remembering all entries to backlog because of feed abort.')
            self.learn_backlog(feed)

    def add_backlog(self, feed, entry, amount=''):
        """Add single entry to feed backlog

        If :amount: is not specified, entry will only be injected on next execution."""
        snapshot = entry.snapshots.get('after_input')
        if not snapshot:
            if feed.current_phase != 'input':
                # Not having a snapshot is normal during input phase, don't display a warning
                log.warning('No input snapshot available for `%s`, using current state' % entry['title'])
            snapshot = entry
        session = Session()
        expire_time = datetime.now() + parse_timedelta(amount)
        backlog_entry = session.query(BacklogEntry).filter(BacklogEntry.title == entry['title']).\
                                                filter(BacklogEntry.feed == feed.name).first()
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
            backlog_entry.feed = feed.name
            backlog_entry.expire = expire_time
            session.add(backlog_entry)
        session.commit()

    def learn_backlog(self, feed, amount=''):
        """Learn current entries into backlog. All feed inputs must have been executed."""
        for entry in feed.entries:
            self.add_backlog(feed, entry, amount)

    def get_injections(self, feed):
        """Insert missing entries from backlog."""
        entries = []
        feed_backlog = feed.session.query(BacklogEntry).filter(BacklogEntry.feed == feed.name)
        for backlog_entry in feed_backlog.all():
            entry = Entry(backlog_entry.entry)

            # this is already in the feed
            if feed.find_entry(title=entry['title'], url=entry['url']):
                continue
            log.debug('Restoring %s' % entry['title'])
            entries.append(entry)
        if entries:
            log.verbose('Added %s entries from backlog' % len(entries))

        # purge expired
        for backlog_entry in feed_backlog.filter(datetime.now() > BacklogEntry.expire).all():
            log.debug('Purging %s' % backlog_entry.title)
            feed.session.delete(backlog_entry)

        return entries

register_plugin(InputBacklog, 'backlog', builtin=True, api_ver=2)
