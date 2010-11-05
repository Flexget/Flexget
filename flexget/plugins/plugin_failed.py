import logging
from flexget.plugin import register_plugin, register_parser_option
from flexget.manager import Base, Session
from sqlalchemy import Column, Integer, String, Unicode, DateTime
from datetime import datetime

log = logging.getLogger('failed')


class FailedEntry(Base):
    __tablename__ = 'failed'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    tof = Column(DateTime)

    def __init__(self, title, url):
        self.title = title
        self.url = url
        self.tof = datetime.now()

    def __str__(self):
        return '<Failed(title=%s)>' % (self.title)


class PluginFailed(object):
    """
    Provides tracking for failures and related commandline utilities.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, feed):
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
        results = failed.query(FailedEntry).all()
        if not results:
            print 'No failed entries recorded'
        for entry in results:
            print '%16s - %s' % (entry.tof.strftime('%Y-%m-%d %H:%M'), entry.title)
        failed.close()

    # TODO: add reason support
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = Session()
        failedentry = FailedEntry(entry['title'], entry['url'])
        # query item's existence
        if not failed.query(FailedEntry).filter(FailedEntry.title == entry['title']).first():
            failed.add(failedentry)
        # limit item number to 25
        i = 0
        for row in failed.query(FailedEntry).order_by(FailedEntry.tof.desc()).all():
            i += 1
            if (i > 25):
                failed.delete(row)
        failed.commit()
        failed.close()

    def clear_failed(self):
        """Clears list of failed entries"""
        session = Session()
        results = session.query(FailedEntry).all()
        for row in results:
            session.delete(row)
        print 'Cleared %i items.' % len(results)
        session.commit()
        session.close()

    def on_entry_fail(self, feed, entry, reason):
        self.add_failed(entry)

register_plugin(PluginFailed, '--failed', builtin=True)
register_parser_option('--failed', action='store_true', dest='failed', default=0,
                       help='List recently failed entries.')
register_parser_option('--clear', action='store_true', dest='clear_failed', default=0,
                       help='Clear recently failed list.')
