from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging

from sqlalchemy import Column, Integer, Boolean, String, Unicode, DateTime

from flexget import db_schema
from flexget.plugin import priority
from flexget.utils.sqlalchemy_utils import table_add_column

log = logging.getLogger('queue')
Base = db_schema.versioned_base('queue', 2)


@db_schema.upgrade('queue')
def upgrade(ver, session):
    if False:  # ver == 0: disable this, since we don't have a remove column function
        table_add_column('queue', 'last_emit', DateTime, session)
        ver = 1
    if ver < 2:
        # We don't have a remove column for 'last_emit', do nothing
        ver = 2
    return ver


class QueuedItem(Base):
    __tablename__ = 'queue'
    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    added = Column(DateTime)
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

    schema = {'type': 'boolean'}

    def on_task_start(self, task, config):
        # Dict of entries accepted by this plugin {imdb_id: entry} format
        self.accepted_entries = {}

    def matches(self, task, config, entry):
        """This should return the QueueItem object for the match, if this entry is in the queue."""
        raise NotImplementedError

    @priority(127)
    def on_task_filter(self, task, config):
        if config is False:
            return

        for entry in task.entries:
            item = self.matches(task, config, entry)
            if item and item.id not in self.accepted_entries:
                # Accept this entry if it matches a queue item that has not been accepted this run yet
                entry.accept(reason='Matches %s queue item: %s' % (item.discriminator, item.title))
                # Keep track of entries we accepted, so they can be marked as downloaded on task_exit if successful
                self.accepted_entries[item.id] = entry

    def on_task_learn(self, task, config):
        if config is False:
            return

        for id, entry in self.accepted_entries.iteritems():
            if entry in task.accepted and entry not in task.failed:
                # If entry was not rejected or failed, mark it as downloaded
                update_values = {'downloaded': datetime.now(),
                                 'entry_title': entry['title'],
                                 'entry_url': entry['url'],
                                 'entry_original_url': entry['original_url']}
                task.session.query(QueuedItem).filter(QueuedItem.id == id).update(update_values)
                log.debug('%s was successful, removing from imdb-queue' % entry['title'])
