import logging
from flexget.manager import Base
from flexget.plugin import *
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, PickleType

log = logging.getLogger('delay')

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
    """
    def validator(self):
        # TODO: make a regexp validation
        from flexget import validator
        return validator.factory('text')
    
    def get_amount(self, feed):
        amount, unit = feed.config.get('backlog').split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit:int(amount)}
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
        for backlog_entry in feed.session.query(BacklogEntry).filter(BacklogEntry.feed == feed.name).all():
            entry = backlog_entry.entry
            # this is already in the feed
            if feed.find_entry(title=entry['title'], url=entry['url']):
                continue
            log.debug('Restoring %s' % entry['title'])
            feed.entries.append(entry)

    def learn_backlog(self, feed):
        """Learn current entries into backlog. All feed inputs must have been executed."""
        expire_time = datetime.now() + self.get_amount(feed)
        for entry in feed.entries:
            if not feed.session.query(BacklogEntry).filter(BacklogEntry.title == entry['title']).\
                                                    filter(BacklogEntry.feed == feed.name).first():
                log.debug('Saving %s' % entry['title'])
                backlog_entry = BacklogEntry()
                backlog_entry.title = entry['title']
                backlog_entry.entry = entry
                backlog_entry.feed = feed.name
                backlog_entry.expire = expire_time
                feed.session.add(backlog_entry)        
        
    def on_feed_input(self, feed):
        self.inject_backlog(feed)
            
    def on_feed_filter(self, feed):
        self.learn_backlog(feed)

register_plugin(InputBacklog, 'backlog', priorities=dict(input=-250, filter=255))
