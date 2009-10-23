import logging
from flexget.plugin import *
from flexget.manager import Base
from sqlalchemy import Table, Column, Integer, Float, String, DateTime, Boolean
import urllib2
import re
import datetime
from flexget.utils.imdb import extract_id

log = logging.getLogger('imdb_queue')

class ImdbQueue(Base):

    __tablename__ = 'imdb_queue'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    quality = Column(String)
    immortal = Column(Boolean)
    added = Column(DateTime)

    def __init__(self, imdb_id, quality, immortal=False):
        self.imdb_id = imdb_id
        self.quality = quality
        self.immortal = immortal
        self.added = datetime.datetime.now()

    def __str__(self):
        return '<ImdbQueue(%s qual %s)>' % (self.imdb_id, self.quality)

class FilterImdbQueue:
    """
    Allows a queue of upcoming movies that will be forcibly allowed if the given quality matches

    Example:

    imdb_queue: yes
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_filter(self, feed):
        log.debug("imdb queue run")
        for entry in feed.entries:
            # make sure the entry has IMDB fields filled
            try:
                get_plugin_by_name('imdb_lookup').instance.lookup(feed, entry)
            except PluginError:
                # no IMDB data, can't do anything
                continue

            # entry has imdb url
            if 'imdb_url' in entry:
                # get an imdb id
                if 'imdb_id' in entry and entry['imdb_id'] != None:
                    imdb_id = entry['imdb_id']
                else:
                    log.debug("Entry has no ID, calculating...")
                    imdb_id = extract_id(entry['imdb_url'])

                if not imdb_id: 
                    log.warning("No imdb id could be determined for %s" % entry['title'])
                    return

                # TODO: Check for quality
                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
                if item:
                    log.info("Accepting %s from queue" % entry['title'])
                    # entry is in the database, accept over all other filters
                    entry['immortal'] = item.immortal
                    feed.accept(entry)
                    # and remove from database
                    feed.session.delete(item)
                else:
                    log.debug("%s not in queue, skipping" % entry['title'])

            feed.session.commit()
            
class ImdbQueueAdd:
    """
    Add item to IMDb queue with an optional quality specifier
    """

    def on_process_start(self, feed):
        if feed.manager.options.imdb_queue_url:
            feed.manager.disable_feeds()
            
            from flexget.manager import Session

            session = Session()            

            imdb_id = extract_id(feed.manager.options.imdb_queue_url)
            quality = feed.manager.options.imdb_queue_quality

            # check if the item is already queued
            item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
            if not item:
                item = ImdbQueue(imdb_id, quality, True)
                session.add(item)
                log.debug("Added %s to queue with quality %s" % (imdb_id, quality))
            else:
                log.info("%s is already in the queue" % imdb_id)

            session.commit()
        

class ImdbQueueList:
    """
    List IMDb queue url + quality

    TODO: Maybe get movie name from DB or something? Parse the page with utils.imdb when adding
    """

    def on_process_start(self, feed):
        if feed.manager.options.imdb_queue_list:
            feed.manager.disable_feeds()
            
            from flexget.manager import Session
            session = Session()            

            # check if the item is already queued
            items = session.query(ImdbQueue)
            for item in items:
                print "http://www.imdb.com/title/"+item.imdb_id, item.quality


register_plugin(FilterImdbQueue, 'imdb_queue', priorities={'filter': 129})
register_plugin(ImdbQueueAdd, 'imdb_queue_add', builtin=True)
register_plugin(ImdbQueueList, 'imdb_queue_list', builtin=True)

register_parser_option('--imdb-queue', action='store', dest='imdb_queue_url', metavar="IMDB_URL",
                       default=False, help="Add movie to queue")
register_parser_option('--imdb-queue-list', action='store_true', dest='imdb_queue_list',
                       default=False, help="List movie queue")
register_parser_option('--imdb-queue-quality', action='store', dest='imdb_queue_quality', metavar="QUALITY", 
                       default="dvdrip", help="Specify movie quality for the queue")
