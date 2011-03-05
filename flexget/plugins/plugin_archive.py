import logging
from flexget.event import event
from flexget.manager import Base
from flexget.plugin import *
from flexget.feed import Entry
from sqlalchemy import Column, Integer, String, DateTime, Unicode, Index, asc, or_
from sqlalchemy.orm import join
from datetime import datetime
from flexget.manager import Session
from optparse import SUPPRESS_HELP

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


def search(session, text):
    """Search by :text: from archive"""
    keyword = unicode(text).replace(' ', '%')
    return session.query(ArchiveEntry).filter(or_(ArchiveEntry.title.like('%' + keyword + '%'),
        ArchiveEntry.feed == keyword)).all()


class ArchiveSearch(object):

    def on_process_start(self, feed):
        if not feed.manager.options.archive_search:
            return

        from flexget.utils.tools import strip_html

        feed.manager.disable_feeds()

        def print_ae(ae):
            diff = datetime.now() - ae.added

            print 'ID: %-6s | Feed: %-10s | Title: %s\nAdded: %s (%d days ago)\nURL: %s' % (ae.id, ae.feed, ae.title, ae.added, diff.days, ae.url)
            if ae.description:
                print 'Description: %s' % strip_html(ae.description)
            print '---'

        session = Session()
        try:
            print 'Searching ...'
            for ae in search(session, feed.manager.options.archive_search):
                print_ae(ae)
        finally:
            session.close()


@event('manager.execute.started')
def reset_archive_inject(manager):
    log.debug('reseting injection')
    ArchiveInject.inject_entries = []


class ArchiveInject(object):

    inject_entries = []

    @priority(512)
    def on_process_start(self, feed):
        inject_ids = feed.manager.options.archive_inject_id
        if not inject_ids:
            return

        # get the entries to be injected
        if not self.inject_entries:
            session = Session()
            try:
                for id_str in inject_ids.split(','):
                    try:
                        id = int(id_str.strip())
                    except ValueError:
                        raise PluginError('Given ID `%s` is not a valid number' % id_str.strip())
                    archive_entry = session.query(ArchiveEntry).filter(ArchiveEntry.id == id).first()
                    
                    # not found
                    if not archive_entry:
                        log.critical('There\'s no archive with ID `%s`' % id)
                        continue
                        
                    # feed no longer exists
                    if archive_entry.feed not in feed.manager.feeds:
                        log.critical('Feed `%s` does not seem to exists anymore, cannot inject from archive' % archive_entry.feed)
                        continue
                                    
                    self.inject_entries.append(archive_entry)
            finally:
                session.close()
                
        # if this feed is not going to be injected into, abort it
        injecting_into = [x.feed for x in self.inject_entries]
        log.debug('injecting_into=%s' % injecting_into)
        if feed.name not in injecting_into:
            log.debug('not injecting to %s, aborting, disabling' % feed.name)
            feed.enabled = False
            feed.abort(silent=True)
        else:
            log.debug('injecting to %s, keeping it' % feed.name)

    @priority(255)
    def on_feed_input(self, feed):
        if not feed.manager.options.archive_inject_id:
            return

        # disable other inputs
        log.info('Disabling all other inputs in the feed.')
        feed.disable_phase('input')

        for inject_entry in self.inject_entries:
            if inject_entry.feed != feed.name:
                # wrong feed, continue to next item
                continue
            log.info('Injecting from archive `%s`' % inject_entry.title)
            entry = Entry(inject_entry.title, inject_entry.url)
            if inject_entry.description:
                entry['description'] = inject_entry.description
            if feed.manager.options.archive_inject_immortal:
                log.debug('Injecting as immortal')
                entry['immortal'] = True
            feed.entries.append(entry)
            feed.accept(entry, '--archive-inject')


class Archive(object):
    """
    Archives all seen items into database where they can be later searched and injected.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(-255)
    def on_feed_input(self, feed):
        """Add new entries into archive"""
        for entry in feed.entries:
            if feed.session.query(ArchiveEntry).\
               filter(ArchiveEntry.title == entry['title']).\
               filter(ArchiveEntry.feed == feed.name).first():
                log.debug('Entry `%s` already archived' % entry['title'])
                continue
            ae = ArchiveEntry()
            ae.title = entry['title']
            ae.url = entry['url']
            if 'description' in entry:
                ae.description = entry['description']
            ae.feed = feed.name
            log.debug('Adding `%s` to archive' % ae)
            feed.session.add(ae)
            
            
class UrlrewriteArchive(object):

    def search(self, feed, entry):
        """Search plugin API method"""
        log.debug('looking for %s' % entry['title'])
        results = search(feed.session, entry['title'])

        # TODO: some logic to return best match? what about quality?
        if results:
            log.debug('found %s' % results)
            return results[0].url
                                

def archive_inject(option, opt, value, parser):
    """Option parser function"""
    
    if not parser.rargs:
        print 'Usage: --archive-inject ID [IMMORTAL]'
        import sys
        sys.exit(1)

    parser.values.archive_inject_id = parser.rargs[0]

    if len(parser.rargs) >= 2:
        from flexget.utils.tools import str_to_boolean
        parser.values.archive_inject_immortal = str_to_boolean(parser.rargs[1])


register_plugin(Archive, 'archive')
register_plugin(UrlrewriteArchive, 'flexget_archive', groups=['search'])
register_plugin(ArchiveSearch, '--archive-search', builtin=True)
register_plugin(ArchiveInject, '--archive-inject', builtin=True)

register_parser_option('--archive-search', action='store', dest='archive_search', default=False,
                       metavar='TXT', help='Search from the archive.')
register_parser_option('--archive-inject', action='callback', callback=archive_inject,
                       metavar='ID(s)', 
                       help='Inject entries from the archive into a feed where it was archived from. Usage: ID[,ID] [FORCE]')

# kludge to make these option keys available always, even when not using archive_inject callback
register_parser_option('--archive-inject-id', action='store', dest='archive_inject_id', default=False,
                       help=SUPPRESS_HELP)
register_parser_option('--archive-inject-immortal', action='store', dest='archive_inject_immortal', default=False,
                       help=SUPPRESS_HELP)
