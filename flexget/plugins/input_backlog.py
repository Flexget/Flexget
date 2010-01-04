import logging
from flexget.manager import Base
from flexget.plugin import *
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, PickleType

log = logging.getLogger('backlog')


class BacklogEntry(Base):
    
    __tablename__ = 'backlog'
    
    id = Column(Integer, primary_key=True)
    feed = Column(String)
    title = Column(String)
    expire = Column(DateTime)
    entry = Column(PickleType)

    def __repr__(self):
        return '<BacklogEntry(title=%s)>' % (self.title)


class InputBacklog:
    """
    Keeps feed history for given amount of time.

    Example:

    backlog: 4 days

    Rarely useful for end users, mainly used by other plugins.
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('regexp_match')
        root.accept('\d+ (minutes|hours|days|weeks)')
    
    def get_amount(self, value):
        amount, unit = value.split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit: int(amount)}
        try:
            return timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format', log)
        
    def inject_backlog(self, feed):
        """Insert missing entries from backlog."""
        # purge expired
        for backlog_entry in feed.session.query(BacklogEntry).filter(datetime.now() > BacklogEntry.expire).all():
            log.debug('Purging %s' % backlog_entry.title)
            feed.session.delete(backlog_entry)
        
        # add missing from backlog
        count = 0
        for backlog_entry in feed.session.query(BacklogEntry).filter(BacklogEntry.feed == feed.name).all():
            # we don't want changes to reflect back into database
            # this is because it causes bugs if entry gets say series parser instance..
            import copy
            entry = copy.deepcopy(backlog_entry.entry)
            # this is already in the feed
            if feed.find_entry(title=entry['title'], url=entry['url']):
                continue
            log.debug('Restoring %s' % entry['title'])
            count += 1
            feed.entries.append(entry)
        if count:
            log.info('Injected %s entries from backlog' % count)

    def learn_backlog(self, feed, amount=''):
        """Learn current entries into backlog. All feed inputs must have been executed."""
        for entry in feed.entries:
            self.add_backlog(feed, entry, amount)

    def add_backlog(self, feed, entry, amount=''):
        """Add single entry to feed backlog"""
        expire_time = datetime.now() + self.get_amount(feed.config.get('backlog', amount))
        if not feed.session.query(BacklogEntry).filter(BacklogEntry.title == entry['title']).\
                                                filter(BacklogEntry.feed == feed.name).first():
            log.debug('Saving %s' % entry['title'])
            backlog_entry = BacklogEntry()
            backlog_entry.title = entry['title']
            backlog_entry.entry = entry
            backlog_entry.feed = feed.name
            backlog_entry.expire = expire_time
            feed.session.add(backlog_entry)
        
    on_feed_input = inject_backlog
    on_feed_filter = learn_backlog
            

register_plugin(InputBacklog, 'backlog', priorities=dict(input=-250, filter=255))
