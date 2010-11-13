import logging
from sqlalchemy import Column, Integer, DateTime, Unicode
from datetime import datetime
from flexget.plugin import register_plugin, priority
from flexget.manager import Base
from flexget.utils.log import log_once
from fnmatch import fnmatch
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

log = logging.getLogger('content_filter')


class CFEntry(Base):

    __tablename__ = 'content_filter'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(Unicode)
    feed = Column(Unicode)
    added = Column(DateTime)
    files = relation('CFFile', backref='entry', cascade='all, delete, delete-orphan')

    def __init__(self):
        self.added = datetime.now()

    def __str__(self):
        return '<CFEntry(title=%s,feed=%s,url=%s,added=%s)>' % (self.title, self.feed, self.url, \
            self.added)

    __repr__ = __str__


class CFFile(Base):

    __tablename__ = 'content_filter_files'

    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey('content_filter.id'), nullable=False)
    name = Column(Unicode)

    def __init__(self, name):
        self.name = name


class FilterContentFilter(object):
    """
    Rejects entries based on the filenames in the content. Torrent files only right now.

    Example:
    content_filter:
      require:
        - '*.avi'
        - '*.mkv'
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='require')
        config.accept('list', key='requrire').accept('text')
        config.accept('text', key='reject')
        config.accept('list', key='reject').accept('text')
        config.accept('boolean', key='strict')
        return config

    def get_config(self, feed):
        config = feed.config.get('content_filter')
        for key in ['require', 'reject']:
            if key in config:
                if isinstance(config[key], basestring):
                    config[key] = [config[key]]
        return config

    def process_entry(self, feed, entry):
        config = self.get_config(feed)
        if 'content_files' in entry:
            files = entry['content_files']
            log.debug('%s files: %s' % (entry['title'], files))

            def matching_mask(files, masks):
                """Returns matching mask if any files match any of the masks, false otherwise"""
                for file in files:
                    for mask in masks:
                        if fnmatch(file, mask):
                            return mask
                return False

            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if config.get('require'):
                if not matching_mask(files, config['require']):
                    log_once('Entry %s does not have any of the required filetypes, rejecting', log)
                    feed.reject(entry, 'does not have any of the required filetypes')
            if config.get('reject'):
                mask = matching_mask(files, config['reject'])
                if mask:
                    log_once('Entry %s has banned file %s, rejecting' % (entry['title'], mask), log)
                    feed.reject(entry, 'has banned file %s' % mask)

    def on_feed_filter(self, feed):
        config = self.get_config(feed)
        for entry in feed.entries:
            # check cache
            cached = feed.session.query(CFEntry).\
                filter(CFEntry.feed == feed.name).\
                filter(CFEntry.title == entry['title']).\
                filter(CFEntry.url == entry['url']).first()
            if cached:
                if not cached.files:
                    if config.get('strict'):
                        # if no files were parsed and we are in strict mode, reject
                        feed.reject(entry, 'no content files parsed for entry')
                else:
                    # set files from cache, maybe configuration has changed to allow it ...
                    if not 'content_files' in entry:
                        entry['content_files'] = [item.name for item in cached.files]
                        log.debug('set content_files from cache (%s)' % entry['content_files'])
            else:
                log.log(5, 'no hit from cache (%s)' % entry['title'])

            self.process_entry(feed, entry)

    def parse_torrent_files(self, entry):
        if 'torrent' in entry:
            files = [item['name'] for item in entry['torrent'].get_filelist()]
            if files:
                entry['content_files'] = files

    @priority(150)
    def on_feed_modify(self, feed):
        if feed.manager.options.test or feed.manager.options.learn:
            log.info('Plugin is partially disabled with --test and --learn because content filename information may not be available')
            return

        config = self.get_config(feed)
        for entry in feed.accepted:
            # TODO: I don't know if we can pares filenames from nzbs, just do torrents for now
            # possibly also do compressed files in the future
            self.parse_torrent_files(entry)
            self.process_entry(feed, entry)
            if not 'content_files' in entry and config.get('strict'):
                feed.reject(entry, 'no content files parsed for entry')
            if entry in feed.rejected:
                # record this in database that it can be rejected at filter event next time
                cf = CFEntry()
                cf.title = entry['title']
                cf.url = entry['url']
                cf.feed = feed.name
                feed.session.add(cf)
                if 'content_files' in entry:
                    for file in entry['content_files']:
                        cf.files.append(CFFile(file))
                log.log(5, 'caching %s' % cf)

register_plugin(FilterContentFilter, 'content_filter')
