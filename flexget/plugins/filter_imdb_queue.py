import logging
from flexget.plugin import *
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
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

_imdb_queue = {}
def optik_imdb_queue(option, opt, value, parser):
    """
    Callback for Optik
    --imdb-queue (add|del|list) IMDB-URL [quality]
    """
    if len(parser.rargs) == 0:
        print "Usage: --imdb-queue (add|del|list) [IMDB_URL] [QUALITY]"
        return

    _imdb_queue['action'] = parser.rargs[0].lower()
    
    if len(parser.rargs) == 1:
        return
    # more than 2 args, we've got quality
    if len(parser.rargs) >= 2:
        _imdb_queue['imdb_url'] = parser.rargs[1]

    if len(parser.rargs) >= 3:
        _imdb_queue['quality'] = parser.rargs[2]
    else:
        _imdb_queue['quality'] = 'dvd' # TODO: Get defaul from config somehow?

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
                    continue

                if not 'quality' in entry:
                    log.warning("No quality found for %s, skipping..." % entry['title'])
                    continue

                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).filter(ImdbQueue.quality == entry['quality']).first()
                if item:
                    log.info("Accepting %s from queue with quality %s" % (entry['title'], entry['quality']))
                    # entry is in the database, accept over all other filters
                    entry['immortal'] = item.immortal
                    feed.accept(entry)
                    # and remove from database
                    feed.session.delete(item)
                else:
                    log.debug("%s not in queue, skipping" % entry['title'])

            feed.session.commit()
            
class ImdbQueueManager:
    """
    Handle IMDb queue management; add, delete and list
    """

    valid_actions = ['add', 'del', 'list']

    def on_process_start(self, feed):
        """
        Handle IMDb queue management
        """
        
        if not _imdb_queue: return

        feed.manager.disable_feeds()

        action = _imdb_queue['action']

        if action not in self.valid_actions:
            self.error("Invalid action, valid actions are: " + ", ".join(self.valid_actions))
            return

        # all actions except list require imdb_url to work
        if action != 'list' and not 'imdb_url' in _imdb_queue:
            self.error("No URL given")
            return
            
        if action == 'add':            
            self.queue_add(_imdb_queue)
            return
        elif action == 'del':
            self.queue_del(_imdb_queue)
            return
        elif action == 'list':
            self.queue_list()
            return

    def error(self, msg):
        print "IMDb Queue error: %s" % msg

    def queue_add(self, queue_item):
        """Add an item to the queue with the specified quality"""

        imdb_id = extract_id(queue_item['imdb_url'])
        quality = queue_item['quality']

        # Check that the quality is valid
        from flexget.utils.titles.parser import TitleParser
        if quality not in TitleParser.qualities:
            print 'Unknown quality: %s' % quality
            return

        from flexget.manager import Session
        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if not item:
            item = ImdbQueue(imdb_id, quality, True)
            session.add(item)
            session.commit()
            print "Added %s to queue with quality %s" % (imdb_id, quality)
        else:
            log.info("%s is already in the queue" % imdb_id)



    def queue_del(self, queue_item):
        """Delete the given item from the queue"""

        imdb_id = extract_id(queue_item['imdb_url'])

        from flexget.manager import Session
        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if item:
            session.delete(item)
            session.commit()
            print "Deleted %s from queue" % (imdb_id)
        else:
            log.info("%s is not in the queue" % imdb_id)

    def queue_list(self):
        """List IMDb queue"""

        from flexget.manager import Session
        session = Session()            

        items = session.query(ImdbQueue)

        found = False

        for item in items:
            found = True
            # TODO: Pretty printing
            print "http://www.imdb.com/title/"+item.imdb_id, item.quality

        if not found:
            print "IMDb queue is empty"
                
register_plugin(FilterImdbQueue, 'imdb_queue', priorities={'filter': 129})
register_plugin(ImdbQueueManager, 'imdb_queue_manager', builtin=True)

register_parser_option('--imdb-queue', action='callback', callback=optik_imdb_queue,
                       help='(add|del|list) [IMDB_URL] [QUALITY]')
