import urllib
import logging
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime, PickleType
from datetime import datetime, timedelta

log = logging.getLogger('seen')

class Seen(Base):
    
    __tablename__ = 'seen'

    id = Column(Integer, primary_key=True)
    field = Column(String)
    value = Column(String)
    feed = Column(String)
    added = Column(DateTime)
    
    def __init__(self, field, value, feed):
        self.field = field
        self.value = value
        self.feed = feed
        self.added = datetime.now()
    
    def __str__(self):
        return '<Seen(%s=%s)>' % (self.field, self.value)

class FilterSeen(object):

    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this plugin FlexGet would
        download all matching content on every execution.

        This plugin is enabled on all feeds by default.
        See wiki for more information.
    """

    def register(self, manager, parser):
        manager.register('seen', builtin=True, filter_priority=255)

        # remember and filter by these fields
        self.fields = ['url', 'title', 'original_url']
        self.keyword = 'seen'

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('text')
        return root

    def feed_filter(self, feed):
        """Filter seen entries"""
        if not feed.config.get('seen', True):
            log.debug('Seen is disabled')
            return
        
        # migrate shelve -> sqlalchemy
        if feed.manager.shelve_session:
            self.migrate(feed)
        
        duplicates = []
        for entry in feed.entries:
            for field in self.fields:
                if not field in entry:
                    continue
                if feed.session.query(Seen).filter(Seen.value == entry[field]).first():
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], field))
                    feed.reject(entry)
                    break

            # scan for duplicates
            for duplicate in feed.entries:
                if entry == duplicate or entry in duplicates: 
                    continue
                for field in self.fields:
                    if field in ['title']:
                        # allow duplicates with these fields
                        continue
                    if not isinstance(entry.get(field, None), basestring):
                        # don't filter based on seen non-string fields like imdb_score!
                        continue
                    if entry.get(field, object()) == duplicate.get(field, object()):
                        log.debug('Rejecting %s because of duplicate field %s' % (duplicate['title'], field))
                        feed.reject(duplicate)
                        # TODO: if / when entry has multiple urls it should combine these two entries
                        # now the duplicate is just rejected and considered seen
                        seen = Seen(field, duplicate[field], feed.name)
                        feed.session.add(seen)
                        duplicates.append(duplicate)

    def feed_exit(self, feed):
        """Remember succeeded entries"""
        if not feed.config.get('seen', True):
            log.debug('disabled')
            return

        for entry in feed.accepted:
            self.learn(feed, entry)
            # verbose if in learning mode
            if feed.manager.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))
    
    def learn(self, feed, entry, fields=[]):
        """Marks entry as seen"""
        if not fields:
            fields = self.fields
        for field in fields:
            if not field in entry:
                continue
            
            seen = Seen(field, entry[field], feed.name)
            feed.session.add(seen)
            
        log.debug("Learned '%s' '%s'" % (entry['url'], entry['title']))
                
    def migrate(self, feed):
        shelve = feed.manager.shelve_session
        count = 0
        for name, data in shelve.iteritems():
            if not self.keyword in data:
                continue
            seen = data[self.keyword]
            for k, v in seen.iteritems():
                seen = Seen('unknown', k, 'unknown')
                feed.session.add(seen)
                count += 1
        log.info('Migrated %s seen items' % count)