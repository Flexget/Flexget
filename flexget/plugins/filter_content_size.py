import logging
from sys import maxint
from sqlalchemy import Column, Integer, DateTime, Unicode, Boolean
from datetime import datetime
from flexget.plugin import register_plugin, priority
from flexget.manager import Base
from flexget.utils.log import log_once

log = logging.getLogger('content_size')


class ContentSize(Base):

    __tablename__ = 'content_size'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(Unicode)
    feed = Column(Unicode)
    size = Column(Integer)
    added = Column(DateTime)
    failed = Column(Boolean)

    def __init__(self):
        self.added = datetime.now()

    def __str__(self):
        return '<ContentSize(title=%s,feed=%s,url=%s,added=%s,failed=%s)>' % (self.title, self.feed, self.url, \
            self.added, self.failed)

    __repr__ = __str__


class FilterContentSize(object):

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        config.accept('boolean', key='strict')
        return config

    def process_entry(self, feed, entry):
        config = feed.config.get('content_size', {})
        if 'content_size' in entry:
            size = entry['content_size']
            log.debug('%s size %s MB' % (entry['title'], size))
            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if size < config.get('min', 0):
                log_once('Entry `%s` too small, rejecting' % entry['title'], log)
                feed.reject(entry, 'minimum size %s MB, got %s MB' % (config['min'], size))
                return True
            if size > config.get('max', maxint):
                log_once('Entry `%s` too big, rejecting' % entry['title'], log)
                feed.reject(entry, 'maximum size %s MB, got %s MB' % (config['max'], size))
                return True

    @priority(150)
    def on_feed_filter(self, feed):
        for entry in feed.entries:
            # check cache
            cached = feed.session.query(ContentSize).\
                filter(ContentSize.feed == feed.name).\
                filter(ContentSize.title == entry['title']).\
                filter(ContentSize.url == entry['url']).first()
            if cached:
                if cached.failed:
                    # this will fail, prevent it even from being downloaded
                    feed.reject(entry, 'content_size check failed')
                else:
                    # set size from cache, maybe configuration has changed to allow it ...
                    if not 'content_size' in entry:
                        entry['content_size'] = cached.size
                        log.debug('set content_size from cache (%s MB)' % cached.size)
            else:
                log.log(5, 'no hit from cache (%s)' % entry['title'])

            self.process_entry(feed, entry)

    @priority(150)
    def on_feed_modify(self, feed):
        if feed.manager.options.test or feed.manager.options.learn:
            log.info('Plugin is partially disabled with --test and --learn because size information may not be available')
            return

        config = feed.config.get('content_size', {})
        for entry in feed.accepted:
            failed = False
            if 'content_size' in entry:
                rejected = self.process_entry(feed, entry)
                if rejected:
                    # rerun only when in modify phase, this is when we have actually downloaded something
                    # to determine what is the size, in filter phase previously filtered items are already
                    # rejected, ie. this effectively affects only new items
                    feed.rerun()
            else:
                if config.get('strict', True):
                    failed = True
                    log.debug('Entry %s size is unknown, rejecting because of strict mode (default)' % entry['title'])
                    log.info('No size information available for %s, rejecting' % entry['title'])
                    if not 'file' in entry:
                        feed.reject(entry, 'no size available, file unavailable')
                        # TODO: download the file and retry? it may not be present if we for example pass
                        #       downloads directly to transmission / deluge
                    else:
                        feed.reject(entry, 'no size available from downloaded file')

            # learn this as seen that it won't be re-downloaded & rejected on every execution
            if entry in feed.rejected:
                cs = ContentSize()
                cs.title = entry['title']
                cs.url = entry['url']
                cs.feed = feed.name
                if 'content_size' in entry:
                    cs.size = entry['content_size']
                else:
                    cs.size = -1
                cs.failed = failed

                log.log(5, 'caching %s' % cs)
                feed.session.add(cs)

register_plugin(FilterContentSize, 'content_size')
