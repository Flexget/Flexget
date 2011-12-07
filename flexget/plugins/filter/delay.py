import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Unicode, DateTime, PickleType, Index
from flexget import schema
from flexget.entry import Entry
from flexget.plugin import register_plugin, priority, PluginError
from flexget.utils.database import safe_pickle_synonym
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('delay')
Base = schema.versioned_base('delay', 1)


class DelayedEntry(Base):

    __tablename__ = 'delay'

    id = Column(Integer, primary_key=True)
    feed = Column(String)
    title = Column(Unicode)
    expire = Column(DateTime)
    _entry = Column('entry', PickleType(mutable=False))
    entry = safe_pickle_synonym('_entry')

    def __repr__(self):
        return '<DelayedEntry(title=%s)>' % self.title

Index('delay_feed_title', DelayedEntry.feed, DelayedEntry.title)
# TODO: index "expire, feed"


@schema.upgrade('delay')
def upgrade(ver, session):
    if ver is None:
        log.info('Fixing delay table from erroneous data ...')
        # TODO: Using the DelayedEntry object here is no good.
        all = session.query(DelayedEntry).all()
        for de in all:
            for key, value in de.entry.iteritems():
                if not isinstance(value, (basestring, bool, int, float, list, dict)):
                    log.warning('Removing `%s` with erroneous data' % de.title)
                    session.delete(de)
                    break
        ver = 1
    return ver


class FilterDelay(object):
    """
        Add delay to a feed. This is useful for de-prioritizing expensive / bad-quality feeds.

        Format: n [minutes|hours|days|weeks]

        Example:

        delay: 2 hours
    """

    def validator(self):
        from flexget import validator
        return validator.factory('interval')

    def get_delay(self, config):
        log.debug('delay: %s' % config)
        try:
            return parse_timedelta(config)
        except ValueError:
            raise PluginError('Invalid time format', log)

    @priority(-1)
    def on_feed_input(self, feed, config):
        """Captures the current input then replaces it with entries that have passed the delay."""
        log.debug('Delaying new entries for %s' % config)
        # First learn the current entries in the feed to the database
        expire_time = datetime.now() + self.get_delay(config)
        for entry in feed.entries:
            log.debug('Delaying %s' % entry['title'])
            # check if already in queue
            if not feed.session.query(DelayedEntry).\
                   filter(DelayedEntry.title == entry['title']).\
                   filter(DelayedEntry.feed == feed.name).first():
                delay_entry = DelayedEntry()
                delay_entry.title = entry['title']
                delay_entry.entry = entry
                delay_entry.feed = feed.name
                delay_entry.expire = expire_time
                feed.session.add(delay_entry)

        # Clear the current entries from the feed now that they are stored
        feed.entries = []

        # Generate the list of entries whose delay has passed
        passed_delay = feed.session.query(DelayedEntry).\
            filter(datetime.now() > DelayedEntry.expire).\
            filter(DelayedEntry.feed == feed.name)
        delayed_entries = [Entry(item.entry) for item in passed_delay.all()]
        for entry in delayed_entries:
            entry['passed_delay'] = True
            log.debug('Releasing %s' % entry['title'])
        # Delete the entries from the db we are about to inject
        passed_delay.delete()

        # Return our delayed entries
        return delayed_entries


register_plugin(FilterDelay, 'delay', api_ver=2)
