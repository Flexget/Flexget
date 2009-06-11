import urllib2
import logging
from flexget.feed import Entry
from flexget.manager import Base
from flexget.plugin import PluginWarning
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, PickleType
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation,join

log = logging.getLogger('delay')

class DelayedEntry(Base):
    
    __tablename__ = 'delay'
    
    id = Column(Integer, primary_key=True)
    feed = Column(String)
    title = Column(String)
    expire = Column(DateTime)
    entry = Column(PickleType)

    def __repr__(self):
        return '<DelayedEntry(title=%s)>' % (self.title)

class FilterDelay:
    """
        Add delay to a feed. This is usefull for de-priorizing expensive / bad-quality feeds.
        
        Format: [n] [minutes|hours|days|months]
        
        Example:
        
        delay: 2 hours
    """

    __plugin__ = 'delay'
    __priorities__ = {
        'filter': 250
    }

    def validator(self):
        # TODO: make a regexp validation
        from flexget import validator
        return validator.factory('text')
    
    def get_delay(self, feed):
        amount, unit = feed.config.get('delay').split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit:int(amount)}
        try:
            return timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format', log)

    def feed_input(self, feed):
        entries = feed.session.query(DelayedEntry).filter(datetime.now() > DelayedEntry.expire).\
                                     filter(DelayedEntry.feed == feed.name).all()
        for delayed_entry in entries:
            entry = delayed_entry.entry
            log.debug('Releasing %s' % entry['title'])
            # internal flag
            entry['passed_delay'] = True
            # if there is same entry already in the feed, remove it to reduce confusion
            for fe in feed.entries[:]:
                if fe['title'] == entry['title']:
                    feed.entries.remove(fe)
            # add expired entry
            feed.entries.append(entry)
            # remove from queue
            feed.session.delete(delayed_entry)
        
    def feed_filter(self, feed):
        expire_time = datetime.now() + self.get_delay(feed)
        for entry in feed.entries:
            if 'passed_delay' in entry:
                continue
            # check if already in queue
            if feed.session.query(DelayedEntry).filter(DelayedEntry.title == entry['title']).\
                                  filter(DelayedEntry.feed == feed.name).first():
                feed.reject(entry, 'in delay')
            else:
                delay_entry = DelayedEntry()
                delay_entry.title = entry['title']
                delay_entry.entry = entry
                delay_entry.feed = feed.name
                delay_entry.expire = expire_time
                feed.reject(entry, 'delaying')
                feed.session.add(delay_entry)
