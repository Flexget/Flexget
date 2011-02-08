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
        ArchiveEntry.title.like('%' + keyword + '%'), ArchiveEntry.feed == keyword)).all()


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
    log.debug('reseting complaint flag')
    ArchiveInject.inject_entry = None


class ArchiveInject(object):

    inject_entry = None

    @priority(512)
    def on_process_start(self, feed):
        inject_id = feed.manager.options.archive_inject_id
        if not inject_id:
            return

        # get the entry to be injected
        if not self.inject_entry:
            session = Session()
            try:
                self.inject_entry = session.query(ArchiveEntry).filter(ArchiveEntry.id == inject_id).first()
                if not self.inject_entry:
                    raise PluginError('There\'s no archive with ID `%s`' % inject_id)
            finally:
                session.close()

            if self.inject_entry.feed not in feed.manager.feeds:
                log.critical('Feed `%s` does not seem to exists anymore, cannot inject from archive' % self.inject_entry.feed)

        if feed.name != self.inject_entry.feed:
            feed.enabled = False
            feed.abort(silent=True)

    @priority(255)
    def on_feed_input(self, feed):
        if not feed.manager.options.archive_inject_id:
            return

        if self.inject_entry.feed != feed.name:
            raise PluginError('BUG: Feed disabling has failed')

        # disable other inputs
        for input in get_plugins_by_phase('input'):
            if input.name in feed.config:
                phases = get_phases_by_plugin(input.name)
                if len(phases) == 1:
                    log.info('Disabling plugin %s' % input.name)
                    del(feed.config[input.name])

        log.info('Injecting %s' % self.inject_entry.title)
        entry = Entry(self.inject_entry.title, self.inject_entry.url)
        if self.inject_entry.description:
            entry['description'] = self.inject_entry.description
        if feed.manager.options.archive_inject_immortal:
            log.debug('Injecting as immortal')
            entry['immortal'] = True
        feed.entries.append(entry)
        feed.accept(entry, '--archive-inject')


class Archive(object):
    """
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
                log.debug('Entry %s already archived' % entry['title'])
                continue
            ae = ArchiveEntry()
            ae.title = entry['title']
            ae.url = entry['url']
            if 'description' in entry:
                ae.description = entry['description']
            ae.feed = feed.name
            log.debug('Adding %s to archive' % ae)
            feed.session.add(ae)


def archive_inject(option, opt, value, parser):
    import sys

    if not parser.rargs:
        print 'Usage: --archive-inject ID [IMMORTAL]'
        sys.exit(1)

    try:
        parser.values.archive_inject_id = int(parser.rargs[0])
    except:
        print 'Value %s is not valid ID' % parser.rargs[0]
        sys.exit(1)

    if len(parser.rargs) >= 2:
        from flexget.utils.tools import str_to_boolean
        parser.values.archive_inject_immortal = str_to_boolean(parser.rargs[1])


register_plugin(Archive, 'archive')
register_plugin(ArchiveSearch, '--archive-search', builtin=True)
register_plugin(ArchiveInject, '--archive-inject', builtin=True)

register_parser_option('--archive-search', action='store', dest='archive_search', default=False,
                       metavar='TXT', help='Search from the archive.')
register_parser_option('--archive-inject', action='callback', callback=archive_inject,
                       metavar='ID', help='Inject entry from the archive into a feed where it was archived from. Usage: ID [IMMORTAL]')

# kludge to make these option keys available always, even when not using archive_inject callback
register_parser_option('--archive-inject-id', action='store', dest='archive_inject_id', default=False,
                       help=SUPPRESS_HELP)
register_parser_option('--archive-inject-immortal', action='store', dest='archive_inject_immortal', default=False,
                       help=SUPPRESS_HELP)
