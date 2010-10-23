import logging
import datetime
from flexget.manager import Session
from flexget.plugin import register_plugin, PluginError, get_plugin_by_name, priority, register_parser_option
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Unicode
from flexget.utils.imdb import extract_id, ImdbSearch, ImdbParser, log as imdb_log
from flexget.utils.tools import str_to_boolean

log = logging.getLogger('imdb_queue')


class ImdbQueue(Base):

    __tablename__ = 'imdb_queue'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    quality = Column(String)
    title = Column(Unicode)
    immortal = Column(Boolean)
    added = Column(DateTime)

    def __init__(self, imdb_id, quality, immortal):
        self.imdb_id = imdb_id
        self.quality = quality
        self.immortal = immortal
        self.added = datetime.datetime.now()

    def __str__(self):
        return '<ImdbQueue(imdb_id=%s,quality=%s,force=%s)>' % (self.imdb_id, self.quality, self.immortal)


class FilterImdbQueue(object):
    """
    Allows a queue of upcoming movies that will be forcibly allowed if the given quality matches

    Example:

    imdb_queue: yes
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(129)
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
                if 'imdb_id' in entry and entry['imdb_id'] is not None:
                    imdb_id = entry['imdb_id']
                else:
                    imdb_id = extract_id(entry['imdb_url'])

                if not imdb_id:
                    log.warning("No imdb id could be determined for %s" % entry['title'])
                    continue

                if not 'quality' in entry:
                    log.warning('No quality found for %s, assigning unknown.' % entry['title'])
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
                    log.log(5, "%s not in queue with wanted quality, skipping" % entry['title'])


class ImdbQueueManager(object):
    """
    Handle IMDb queue management; add, delete and list
    """

    valid_actions = ['add', 'del', 'list']

    options = {}

    @staticmethod
    def optik_imdb_queue(option, opt, value, parser):
        """
        Callback for Optik
        --imdb-queue (add|del|list) [IMDB_URL|NAME] [quality]
        """
        if len(parser.rargs) == 0:
            print 'Usage: --imdb-queue (add|del|list) [IMDB_URL|NAME] [QUALITY] [FORCE]'
            # set some usage option so that feeds will be disabled later
            ImdbQueueManager.options['usage'] = True
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

        if 'usage' in self.options:
            return

        action = self.options['action']
        if action not in self.valid_actions:
            self.error('Invalid action, valid actions are: ' + ', '.join(self.valid_actions))
            return

        # all actions except list require imdb_url to work
        if action != 'list' and not 'what' in self.options:
            self.error('No URL or NAME given')
            return

        from sqlalchemy.exceptions import OperationalError
        try:
            if action == 'add':
                self.queue_add()
            elif action == 'del':
                self.queue_del()
            elif action == 'list':
                self.queue_list()
        except OperationalError:
            log.critical('OperationalError')

    def error(self, msg):
        print 'IMDb Queue error: %s' % msg

    def queue_add(self):
        """Add an item to the queue with the specified quality"""

        # Check that the quality is valid
        quality = self.options['quality']

        from flexget.utils import qualities
        if (quality != 'ANY') and (quality not in qualities.registry):
            print 'ERROR! Unknown quality `%s`' % quality
            print 'Recognized qualities are %s' % ', '.join(qualities.registry.keys())
            print 'ANY is the default and can also be used explicitly to specify that quality should be ignored.'
            return

        imdb_id = extract_id(self.options['what'])
        title = None

        if not imdb_id:
            # try to do imdb search
            print 'Searching imdb for %s' % self.options['what']
            search = ImdbSearch()
            result = search.smart_match(self.options['what'])
            if not result:
                print 'ERROR: Unable to find any such movie from imdb, use imdb url instead.'
                return
            imdb_id = extract_id(result['url'])
            title = result['name']

        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if not item:
            # get the common, eg. 1280x720 will be turned into 720p
            common_name = qualities.common_name(quality)
            item = ImdbQueue(imdb_id, common_name, self.options['force'])
            item.title = title
            session.add(item)
            session.commit()
            print 'Added %s to queue with quality %s' % (imdb_id, common_name)
        else:
            print 'ERROR: %s is already in the queue' % imdb_id

    def queue_del(self):
        """Delete the given item from the queue"""

        imdb_id = extract_id(self.options['what'])

        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if item:
            session.delete(item)
            print 'Deleted %s from the queue' % (imdb_id)
        else:
            log.info('%s is not in the queue' % imdb_id)

        session.commit()

    def queue_list(self):
        """List IMDb queue"""

        session = Session()

        items = session.query(ImdbQueue)
        print '-' * 79
        print '%-10s %-45s %-8s %s' % ('IMDB id', 'Title', 'Quality', 'Force')
        print '-' * 79
        for item in items:
            if not item.title:
                # old database does not have title / title not retrieved
                imdb_log.setLevel(logging.CRITICAL)
                parser = ImdbParser()
                try:
                    result = parser.parse('http://www.imdb.com/title/' + item.imdb_id)
                except:
                    pass
                if parser.name:
                    item.title = parser.name
                else:
                    item.title = 'N/A'
            print '%-10s %-45s %-8s %s' % (item.imdb_id, item.title, item.quality, item.immortal)

        if not items:
            print 'IMDB queue is empty'

        print '-' * 79

        session.commit()
        session.close()

register_plugin(FilterImdbQueue, 'imdb_queue')
register_plugin(ImdbQueueManager, 'imdb_queue_manager', builtin=True)

register_parser_option('--imdb-queue', action='callback', callback=ImdbQueueManager.optik_imdb_queue,
                       help='(add|del|list) [IMDB_URL|NAME] [QUALITY]')
