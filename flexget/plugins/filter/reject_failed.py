import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy.schema import Index, MetaData
from flexget import schema
from flexget.plugin import register_plugin, register_parser_option, priority
from flexget.manager import Session
from flexget.utils.tools import console
from flexget.utils.sqlalchemy_utils import table_add_column

SCHEMA_VER = 1

log = logging.getLogger('failed')
Base = schema.versioned_base('failed', SCHEMA_VER)


@schema.upgrade('failed')
def upgrade(ver, session):
    if ver is None:
        # add count column
        table_add_column('failed', 'count', Integer, session, default=1)
        ver = 0
    if ver == 0:
        # define an index
        log.info('Adding database index ...')
        meta = MetaData(bind=session.connection(), reflect=True)
        failed = meta.tables['failed']
        Index('failed_title_url', failed.c.title, failed.c.url, failed.c.count).create()
        ver = 1
    return ver


class FailedEntry(Base):
    __tablename__ = 'failed'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    tof = Column(DateTime)
    count = Column(Integer, default=1)

    def __init__(self, title, url):
        self.title = title
        self.url = url
        self.tof = datetime.now()

    def __str__(self):
        return '<Failed(title=%s)>' % self.title

# create indexes, used when creating tables
columns = Base.metadata.tables['failed'].c
Index('failed_title_url', columns.title, columns.url, columns.count)


class PluginFailed(object):
    """Provides tracking for failures and related commandline utilities."""

    def on_process_start(self, feed, config):
        if feed.manager.options.failed:
            feed.manager.disable_feeds()
            self.print_failed()
            return
        if feed.manager.options.clear_failed:
            feed.manager.disable_feeds()
            self.clear_failed()
            return

    def print_failed(self):
        """Parameter --failed"""

        failed = Session()
        try:
            results = failed.query(FailedEntry).all()
            if not results:
                console('No failed entries recorded')
            for entry in results:
                console('%16s - %s - %s times' % (entry.tof.strftime('%Y-%m-%d %H:%M'), entry.title, entry.count))
        finally:
            failed.close()

    # TODO: add reason support
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = Session()
        try:
            # query item's existence
            item = failed.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                                             filter(FailedEntry.url == entry['url']).first()
            if not item:
                item = FailedEntry(entry['title'], entry['url'])
            else:
                item.count += 1
                item.tof = datetime.now()
            failed.merge(item)

            # limit item number to 25
            for row in failed.query(FailedEntry).order_by(FailedEntry.tof.desc())[25:]:
                failed.delete(row)
            failed.commit()
        finally:
            failed.close()

    def clear_failed(self):
        """Clears list of failed entries"""
        session = Session()
        try:
            results = session.query(FailedEntry).all()
            for row in results:
                session.delete(row)
            console('Cleared %i items.' % len(results))
            session.commit()
        finally:
            session.close()

    def on_entry_fail(self, feed, entry, **kwargs):
        self.add_failed(entry)


class FilterRejectFailed(object):
    """Rejects entries that have failed X or more times in the past."""

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('integer')
        root.accept('boolean')
        return root

    @priority(255)
    def on_feed_filter(self, feed, config):
        if config is False:
            return
        max_count = 3 if config in [None, True] else config
        for entry in feed.entries:
            item = feed.session.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                                            filter(FailedEntry.url == entry['url']).\
                                            filter(FailedEntry.count >= max_count).first()
            if item:
                feed.reject(entry, 'Has already failed %s times in the past' % item.count)

register_plugin(PluginFailed, '--failed', builtin=True, api_ver=2)
register_plugin(FilterRejectFailed, 'reject_failed', builtin=True, api_ver=2)
register_parser_option('--failed', action='store_true', dest='failed', default=0,
                       help='List recently failed entries.')
register_parser_option('--clear', action='store_true', dest='clear_failed', default=0,
                       help='Clear recently failed list.')
