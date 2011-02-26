import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, PickleType
from flexget.manager import Base, Session
from flexget.feed import Entry
from flexget.plugin import register_plugin, priority, PluginWarning

log = logging.getLogger('backlog')


class BacklogEntry(Base):

    __tablename__ = 'backlog'

    id = Column(Integer, primary_key=True)
    feed = Column(String)
    title = Column(String)
    expire = Column(DateTime)
    entry = Column(PickleType(mutable=False))

    def __repr__(self):
        return '<BacklogEntry(title=%s)>' % (self.title)


class InputBacklog(object):
    """
    Keeps feed history for given amount of time.

    Example:

    backlog: 4 days

    Rarely useful for end users, mainly used by other plugins.
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('regexp_match', message='Must be in format <number> <hours|minutes|days|weeks>')
        root.accept('\d+ (minute|hour|day|week)s?')
        return root

    def get_amount(self, value):
        if not value:
            # If no time is given, default to 0 (entry will only be injected on next execution)
            return timedelta()
        amount, unit = value.split(' ')
        # Make sure unit name is plural.
        if not unit.endswith('s'):
            unit = unit + 's'
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit: int(amount)}
        try:
            return timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format \'%s\'' % value, log)

    @priority(-255)
    def on_feed_input(self, feed, config):
        # Get a list of entries to inject 
        injections = self.get_injections(feed)
        # Take a snapshot of the entries' states after the input event in case we have to store them to backlog
        for entry in feed.entries:
            entry.take_snapshot('after_input')
        if config:
            # If backlog is manually enabled for this feed, learn the entries.
            self.learn_backlog(feed, config)
        # Return the entries from backlog that are not already in the feed
        return injections

    def on_feed_abort(self, feed, config):
        """Remember all entries until next execution when feed gets aborted."""
        log.debug('Remembering all entries to backlog because of feed abort.')
        self.learn_backlog(feed)

    def add_backlog(self, feed, entry, amount=''):
        """Add single entry to feed backlog

        If :amount: is not specified, entry will only be injected on next execution."""
        snapshot = entry.snapshots.get('after_input')
        if not snapshot:
            log.warning('No input snapshot available for `%s`, using current state' % entry['title'])
            snapshot = dict(entry)
        session = Session()
        expire_time = datetime.now() + self.get_amount(amount)
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
            feed.verbose_progress('Added %s entries from backlog' % len(entries), log)

        # purge expired
        for backlog_entry in feed_backlog.filter(datetime.now() > BacklogEntry.expire).all():
            log.debug('Purging %s' % backlog_entry.title)
            feed.session.delete(backlog_entry)

        return entries

register_plugin(InputBacklog, 'backlog', builtin=True, api_ver=2)
