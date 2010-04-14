import logging
from flexget.manager import Base
from flexget.plugin import *
from flexget.feed import Entry
from sqlalchemy import Column, Integer, String, DateTime, Unicode, Index, asc, or_
from sqlalchemy.orm import join
from datetime import datetime
from flexget.manager import Session

log = logging.getLogger('archive')


class ArchiveEntry(Base):

    __tablename__ = 'archive_entry'
    
    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(Unicode, index=True)
    description = Column(Unicode)
    feed = Column(Unicode)
    added = Column(DateTime, index=True)
    
    def __init__(self):
        self.added = datetime.now()
        
    def __str__(self):
        return '<ArchiveEntry(title=%s,url=%s,feed=%s)>' % (self.title, self.url, self.feed)

# create index
columns = Base.metadata.tables['archive_entry'].c
Index('archive_feed_title', columns.feed, columns.title)


class ArchiveSearch(object):

    def on_process_start(self, feed):
        if not feed.manager.options.archive_search:
            return

        feed.manager.disable_feeds()
        
        def print_ae(ae):
            print 'ID: %s Feed: %s Title: %s URL: %s Added: %s' % (ae.id, ae.feed, ae.title, ae.url, ae.added)
            if ae.description:
                print 'Description: %s' % ae.description
            print ''

        session = Session()
        
        keyword = unicode(feed.manager.options.archive_search)
        for ae in session.query(ArchiveEntry).filter(or_(ArchiveEntry.title.like('%' + keyword + '%'), 
            ArchiveEntry.title.like('%' + keyword + '%'), ArchiveEntry.feed == keyword)).all():
            print_ae(ae)

        session.close()


class ArchiveInject(object):

    id = None
    inject_entry = None
    immortal = False
    
    injected = False
    complained = False

    @staticmethod
    def optik(option, opt, value, parser):
        if len(parser.rargs) == 0:
            print 'Usage: --archive-inject ID [IMMORTAL]'
            return

        try:
            ArchiveInject.id = int(parser.rargs[0])
        except:
            print 'Value %s is not valid ID' % parser.rargs[0]
            return            
        if len(parser.rargs) >= 2:
            from flexget.utils.tools import str_to_boolean
            ArchiveInject.immortal = str_to_boolean(parser.rargs[1])

    def on_process_start(self, feed):
        if not self.id:
            return
            
        if not self.inject_entry:
            # get the entry to be injected
            session = Session()
            self.inject_entry = session.query(ArchiveEntry).filter(ArchiveEntry.id == self.id).first()
            if not self.inject_entry:
                raise PluginError('There\'s no archive with ID %s' % self.id)
            session.close()

            # TODO: disable other feeds here, remove aborting from on_feed_input
            
    def on_feed_input(self, feed):
        if not self.inject_entry:
            return
        if self.inject_entry.feed == feed.name:
            
            # disable other inputs
            for input in get_plugins_by_event('input'):
                if input.name in feed.config:
                    events = get_events_by_plugin(input.name)
                    if len(events) == 1:
                        log.info('Disabling plugin %s' % input.name)
                        del(feed.config[input.name])
        
            log.info('Injecting %s' % self.inject_entry.title)
            entry = Entry(self.inject_entry.title, self.inject_entry.url)
            if self.inject_entry.description:
                entry['description'] = self.inject_entry.description
            if self.immortal:
                log.debug('Injecting as immortal')
                entry['immortal'] = True
            feed.entries.append(entry)
            feed.accept(entry, '--archive-inject')
            self.injected = True
        else:
            log.debug('wrong feed, aborting')
            feed.abort(silent=True)
            
    def on_process_end(self, feed):
        if self.inject_entry and not self.injected and not self.complained:
            log.critical('Didn\'t inject the entry, perhaps the original feed %s was not ran?' % self.inject_entry.feed)
            self.complained = True


class Archive(object):
    """
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_input(self, feed):
        """Add new entries into archive"""
        for entry in feed.entries:
            if feed.session.query(ArchiveEntry).\
               filter(ArchiveEntry.title == entry['title']).\
               filter(ArchiveEntry.feed == feed.name).first():
                log.debug('Entry %s already archived' % entry['title'])
                continue
            ae = ArchiveEntry()
            ae.title = entry['title']
            ae.url = entry['url']
            if 'description' in entry:
                ae.description = entry['description']
            ae.feed = feed.name
            log.debug('Addin %s to archive' % ae)
            feed.session.add(ae)
        
register_plugin(Archive, 'archive', builtin=True, priorities=dict(input=-255))
register_plugin(ArchiveSearch, '--archive-search', builtin=True)
register_plugin(ArchiveInject, '--archive-inject', builtin=True, priorities={'input': 255})

register_parser_option('--archive-search', action='store', dest='archive_search', default=False,
                       metavar='TEXT', help='Search from the archive.')
register_parser_option('--archive-inject', action='callback', callback=ArchiveInject.optik,
                       metavar='ID', help='Inject entry from archive to a feed it was archived. Usage: ID [IMMORTAL]')
