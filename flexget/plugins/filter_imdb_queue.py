import logging
import datetime
from flexget.manager import Session
from flexget.plugin import *
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from flexget.utils.imdb import extract_id, ImdbSearch
from flexget.utils.tools import str_to_boolean

log = logging.getLogger('imdb_queue')


class ImdbQueue(Base):

    __tablename__ = 'imdb_queue'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    quality = Column(String)
    immortal = Column(Boolean)
    added = Column(DateTime)

    def __init__(self, imdb_id, quality, immortal):
        self.imdb_id = imdb_id
        self.quality = quality
        self.immortal = immortal
        self.added = datetime.datetime.now()

    def __str__(self):
        return '<ImdbQueue(imdb_id=%s,quality=%s,force=%s)>' % (self.imdb_id, self.quality, self.immortal)


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
                    imdb_id = extract_id(entry['imdb_url'])

                if not imdb_id: 
                    log.warning("No imdb id could be determined for %s" % entry['title'])
                    continue

                if not 'quality' in entry:
                    log.warning("No quality found for %s, assigning unknown." % entry['title'])
                    entry['quality'] = 'unknown'

                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).\
                                                     filter((ImdbQueue.quality == entry['quality']) | (ImdbQueue.quality == "ANY")).first()

                if item:
                    entry['immortal'] = item.immortal
                    log.info("Accepting %s from queue with quality %s. Force: %s" % (entry['title'], entry['quality'], entry['immortal']))
                    feed.accept(entry, 'imdb-queue - force: %s' % entry['immortal'])
                    # and remove from database
                    feed.session.delete(item)
                else:
                    log.debug("%s not in queue, skipping" % entry['title'])


class ImdbQueueManager:
    """
    Handle IMDb queue management; add, delete and list
    """

    valid_actions = ['add', 'del', 'list']

    options = {}

    @staticmethod
    def optik_imdb_queue(option, opt, value, parser):
        """
        Callback for Optik
        --imdb-queue (add|del|list) IMDB-URL [quality]
        """
        if len(parser.rargs) == 0:
            print 'Usage: --imdb-queue (add|del|list) [IMDB_URL|NAME] [QUALITY] [FORCE]'
            return

        ImdbQueueManager.options['action'] = parser.rargs[0].lower()

        if len(parser.rargs) == 1:
            return
        # 2 args is the minimum allowed (operation + item)
        if len(parser.rargs) >= 2:
            ImdbQueueManager.options['what'] = parser.rargs[1]

        # 3, quality
        if len(parser.rargs) >= 3:
            ImdbQueueManager.options['quality'] = parser.rargs[2]
        else:
            ImdbQueueManager.options['quality'] = 'ANY' # TODO: Get default from config somehow?

        # 4, force download
        if len(parser.rargs) >= 4:
            ImdbQueueManager.options['force'] = str_to_boolean(parser.rargs[3])
        else:
            ImdbQueueManager.options['force'] = True

    def on_process_start(self, feed):
        """
        Handle IMDb queue management
        """
        
        if not self.options:
            return

        feed.manager.disable_feeds()

        action = self.options['action']
        if action not in self.valid_actions:
            self.error('Invalid action, valid actions are: ' + ', '.join(self.valid_actions))
            return

        # all actions except list require imdb_url to work
        if action != 'list' and not 'what' in self.options:
            self.error('No URL or NAME given')
            return
            
        if action == 'add':            
            self.queue_add()
        elif action == 'del':
            self.queue_del()
        elif action == 'list':
            self.queue_list()

    def error(self, msg):
        print 'IMDb Queue error: %s' % msg

    def queue_add(self):
        """Add an item to the queue with the specified quality"""

        imdb_id = extract_id(self.options['what'])

        if not imdb_id:
            # try to do imdb search
            print 'Searching imdb for %s' % self.options['what']
            search = ImdbSearch()
            result = search.smart_match(self.options['what'])
            if not result:
                print 'Unable to find any such movie from imdb, use imdb url instead.'
                return
            imdb_id = extract_id(result['url'])

        quality = self.options['quality']

        # Check that the quality is valid
        from flexget.utils.titles.parser import TitleParser
        if (quality != "ANY") and (quality not in TitleParser.qualities):
            print 'Unknown quality: %s' % quality
            print 'Recognized qualities are %s' % ', '.join(TitleParser.qualities)
            print 'ANY is the default, and can also be used explicitly, to specify that quality should be ignored.'
            return

        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if not item:
            item = ImdbQueue(imdb_id, quality, self.options['force'])
            session.add(item)
            session.commit()
            print "Added %s to queue with quality %s" % (imdb_id, quality)
        else:
            log.info("%s is already in the queue" % imdb_id)

    def queue_del(self):
        """Delete the given item from the queue"""

        imdb_id = extract_id(self.options['what'])

        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if item:
            session.delete(item)
            session.commit()
            print 'Deleted %s from queue' % (imdb_id)
        else:
            log.info('%s is not in the queue' % imdb_id)

    def queue_list(self):
        """List IMDb queue"""

        session = Session()            

        items = session.query(ImdbQueue)
        found = False
        print "%-40s %-8s %-5s" % ("URL", "Quality", "Force")
        for item in items:
            found = True
            print "%-40s %-8s %-5s" % ('http://www.imdb.com/title/' + item.imdb_id, item.quality, item.immortal)

        if not found:
            print 'IMDb queue is empty'
                
register_plugin(FilterImdbQueue, 'imdb_queue', priorities={'filter': 129})
register_plugin(ImdbQueueManager, 'imdb_queue_manager', builtin=True)

register_parser_option('--imdb-queue', action='callback', callback=ImdbQueueManager.optik_imdb_queue,
                       help='(add|del|list) [IMDB_URL] [QUALITY]')
