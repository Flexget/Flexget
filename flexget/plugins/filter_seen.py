import logging
from flexget.manager import Base
from flexget.plugin import *
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

log = logging.getLogger('seen')


class Seen(Base):
    
    __tablename__ = 'seen'

    id = Column(Integer, primary_key=True)
    field = Column(String)
    value = Column(String, index=True)
    feed = Column(String)
    added = Column(DateTime)
    
    def __init__(self, field, value, feed):
        self.field = field
        self.value = value
        self.feed = feed
        self.added = datetime.now()
    
    def __str__(self):
        return '<Seen(%s=%s)>' % (self.field, self.value)


class RepairSeen(object):

    """Repair seen database by removing duplicate items."""

    def on_process_start(self, feed):
        if not feed.manager.options.repair_seen:
            return
    
        feed.manager.disable_feeds()
        
        print '-' * 79
        print ' Removing faulty duplicate items from seen database'
        print ' This may take a while ...'
        print '-' * 79
        
        from flexget.manager import Session
        session = Session()
        
        index = 0
        removed = 0
        total = session.query(Seen).count()
        for seen in session.query(Seen).all():
            index += 1
            if (index % 500 == 0):
                print ' %s / %s' % (index, total)
            amount = 0
            for dupe in session.query(Seen).filter(Seen.value == seen.value):
                amount += 1
                if amount > 1:
                    removed += 1
                    session.delete(dupe)
        
        session.commit()
        session.close()

        total = session.query(Seen).count()
        print '-' * 79
        print ' Removed %s duplicates' % removed
        print ' %s items remaining' % total
        print '-' * 79


class SearchSeen(object):

    def on_process_start(self, feed):
        if not feed.manager.options.seen_search:
            return

        feed.manager.disable_feeds()

        print '-- Seen ---------------- Feed --------------  Field ---- Value -----------'

        from flexget.manager import Session
        import time
        session = Session()
        for seen in session.query(Seen).filter(Seen.value.like('%' + feed.manager.options.seen_search + '%')).all():
            print '%-24s %-20s %-10s %s' % (seen.added.strftime('%c'), seen.feed, seen.field, seen.value)

        session.close()


class FilterSeen(object):
    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this plugin FlexGet would
        download all matching content on every execution.

        This plugin is enabled on all feeds by default.
        See wiki for more information.
    """

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['url', 'title', 'original_url']
        self.keyword = 'seen'

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('text')
        return root

    # TODO: separate to own class!
    def on_process_start(self, feed):
        """Implements --forget <feed> and --seen <value>"""

        # migrate shelve -> sqlalchemy
        if feed.manager.shelve_session:
            self.migrate(feed)
        
        if feed.manager.options.forget or feed.manager.options.seen:
            # don't run any feeds
            feed.manager.disable_feeds()
            
            # in process_start the feed.session is not available
            from flexget.manager import Session
        
        if feed.manager.options.forget:

            forget = feed.manager.options.forget

            session = Session()
            count = 0
            for seen in session.query(Seen).filter(Seen.feed == forget):
                session.delete(seen)
                count += 1
                
            for seen in session.query(Seen).filter(Seen.value == forget):
                session.delete(seen)
                count += 1
                
            session.commit()
            
            log.info('Forgot %s memories from %s' % (count, forget))
            
            if count == 0:
                log.info('Perhaps feed / given value does not exists?')
            
        if feed.manager.options.seen:

            session = Session()
            seen = Seen('', feed.manager.options.seen, '--seen')
            session.add(seen)
            session.commit()
            
            log.info('Added %s as seen. This will affect all feeds.' % feed.manager.options.seen)
        
    def on_feed_filter(self, feed):
        """Filter seen entries"""
        if not feed.config.get(self.keyword, True):
            log.debug('%s is disabled' % self.keyword)
            return
        
        queries = 0
        for entry in feed.entries:
            for field in self.fields:
                if not field in entry:
                    continue
                queries += 1
                if feed.session.query(Seen).filter(Seen.value == entry[field]).first():
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], field))
                    feed.reject(entry)
                    break
            else:
                continue
        if feed.manager.options.debug_perf:
            log.info('Executed %s queries' % queries)

    def on_feed_exit(self, feed):
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
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        remembered = []
        for field in fields:
            if not field in entry:
                continue
            if entry[field] in remembered:
                continue
            seen = Seen(field, entry[field], feed.name)
            feed.session.add(seen)
            remembered.append(entry[field])
            log.debug("Learned '%s' (field: %s)" % (entry[field], field))
                
    def migrate(self, feed):
        """Migrates 0.9 session data into new database"""
        from flexget.manager import Session
        session = Session()
        shelve = feed.manager.shelve_session
        count = 0
        for name, data in shelve.iteritems():
            if not self.keyword in data:
                continue
            seen = data[self.keyword]
            for k, v in seen.iteritems():
                seen = Seen('unknown', k, 'unknown')
                session.add(seen)
                count += 1
        session.commit()
        log.info('Migrated %s seen items' % count)

register_plugin(FilterSeen, 'seen', builtin=True, priorities=dict(filter=255))
register_plugin(RepairSeen, '--repair-seen', builtin=True)
register_plugin(SearchSeen, '--seen-search', builtin=True)

register_parser_option('--forget', action='store', dest='forget', default=False,
                       metavar='FEED|VALUE', help='Forget feed (completely) or given title or url.')
register_parser_option('--seen', action='store', dest='seen', default=False,
                       metavar='VALUE', help='Add title or url to what has been seen in feeds.')
register_parser_option('--repair-seen', action='store_true', dest='repair_seen', default=False,
                       help='Repair seen database by removing duplicate lines.')
register_parser_option('--seen-search', action='store', dest='seen_search', default=False,
                       metavar='VALUE', help='Search given text from seen database.')
