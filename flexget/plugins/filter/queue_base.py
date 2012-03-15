from datetime import datetime
import logging
from sqlalchemy import Column, Integer, Boolean, String, Unicode, DateTime
from flexget.schema import versioned_base
from flexget.plugin import priority

log = logging.getLogger('queue')
Base = versioned_base('queue', 0)


class QueuedItem(Base):
    __tablename__ = 'queue'
    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    added = Column(DateTime)
    immortal = Column(Boolean)
    # These fields are populated when the queue item has been downloaded
    downloaded = Column(DateTime)
    entry_title = Column(Unicode)
    entry_url = Column(Unicode)
    entry_original_url = Column(Unicode)
    # Configuration for joined table inheritance
    discriminator = Column('type', String)
    __mapper_args__ = {'polymorphic_on': discriminator}

    def __init__(self, **kwargs):
        super(QueuedItem, self).__init__(**kwargs)
        self.added = datetime.now()


class FilterQueueBase(object):
    """Base class to handle general tasks of keeping a queue of wanted items."""

    def on_feed_start(self, feed, config):
        # Dict of entries accepted by this plugin {imdb_id: entry} format
        self.accepted_entries = {}

    def validator(self):
        """Default validator just accepts a boolean, can be overridden by subclasses"""
        from flexget import validator
        return validator.factory('boolean')

    def matches(self, feed, config, entry):
        """This should return the QueueItem object for the match, if this entry is in the queue."""
        raise NotImplementedError

    @priority(129)
    def on_feed_filter(self, feed, config):
        if config is False:
            return

        for entry in feed.entries:
            item = self.matches(feed, config, entry)
            if item and item.id not in self.accepted_entries:
                # Accept this entry if it matches a queue item that has not been accepted this run yet
                if item.immortal:
                    entry['immortal'] = True
                feed.accept(entry, reason='Matches %s queue item: %s' % (item.discriminator, item.title))
                # Keep track of entries we accepted, so they can be marked as downloaded on feed_exit if successful
                self.accepted_entries[item.id] = entry

    def on_feed_exit(self, feed, config):
        if config is False:
            return

        for id, entry in self.accepted_entries.iteritems():
            if entry in feed.accepted and entry not in feed.failed:
                # If entry was not rejected or failed, mark it as downloaded
                update_values = {'downloaded': datetime.now(),
                                 'entry_title': entry['title'],
                                 'entry_url': entry['url'],
                                 'entry_original_url': entry['original_url']}
                feed.session.query(QueuedItem).filter(QueuedItem.id == id).update(update_values)
                log.debug('%s was successful, removing from imdb-queue' % entry['title'])
