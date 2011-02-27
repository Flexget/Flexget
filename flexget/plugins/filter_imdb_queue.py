import logging
import datetime
from flexget.manager import Session
from flexget.plugin import register_plugin, PluginError, get_plugin_by_name, priority, register_parser_option, register_feed_phase
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Unicode
from flexget.utils.imdb import extract_id, ImdbSearch, ImdbParser, log as imdb_log
from flexget.utils.tools import str_to_boolean
from flexget.utils import qualities

log = logging.getLogger('imdb_queue')


class QueueError(Exception):
    """Exception raised if there is an error with a queue operation"""

    def __init__(self, message, errno=0):
        self.message = message
        self.errno = errno


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

    # Dict of entries accepted by this plugin {imdb_id: entry} format
    accepted_entries = {}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(129)
    def on_feed_filter(self, feed):
        # Doing this so that I register as a filter plugin. Just need to filter
        # after urlrewrite happens, just before download.
        # Also have to accept anything with an IMDB url that matches, even if
        # rejecting later.
        rejected = []
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

                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()

                if item:
                    entry['immortal'] = item.immortal
                    log.debug("Pre-accepting %s from queue" % (entry['title']))
                    feed.accept(entry, 'imdb-queue pre-accept')
                    # Keep track of entries we accepted, so they can be removed from queue on feed_exit if successful
                    self.accepted_entries[imdb_id] = entry
                else:
                    log.debugall("%s not in queue, skipping" % entry['title'])

    def on_feed_imdbqueue(self, feed):
        rejected = []
        for entry in feed.entries:
            if entry['url'] == '':
                feed.reject(entry, 'imdb-queue - no URL in entry: '
                            '%s' % entry['title'])
                rejected.append(entry['title'])
                continue
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

                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()

                if item:
                    # This will return UnknownQuality if 'ANY' quality
                    minquality = qualities.parse_quality(item.quality)
                    if 'quality' in entry:
                        entry_quality = qualities.parse_quality(entry['quality'])
                    if entry_quality >= minquality:
                        entry['immortal'] = item.immortal
                        log.debug("found %s quality for %s. Need minimum %s" %
                                  (entry['title'], entry['quality'],
                                   item.quality))
                        log.info("Accepting %s from queue with quality %s. Force: %s" % (entry['title'], entry['quality'], entry['immortal']))
                        feed.accept(entry, 'imdb-queue - force: %s' % entry['immortal'])
                        # Keep track of entries we accepted, so they can be removed from queue on feed_exit if successful
                        self.accepted_entries[imdb_id] = entry
                    else:
                        log.debug("imdb-queue rejecting - found "
                                  "%s quality for %s. Need minimum %s" %
                                  (entry['title'], entry['quality'],
                                   item.quality))
                        # Rejecting, as imdb-queue overrides anything. Don't
                        # want to accidentally grab lower quality than desired.
                        entry['immortal'] = False
                        feed.reject(entry, 'imdb-queue quality '
                                    '%s below minimum %s for %s' %
                                    (entry_quality.name, minquality.name,
                                     entry['title']))
                else:
                    log.debugall("%s not in queue with wanted quality, skipping" % entry['title'])
        if len(rejected):
            log.info("Rejected due to no URL in entry (URLRewrite probably failed):"
                     " %s" % ', '.join(rejected))

    def on_feed_exit(self, feed):
        """
        Removes any entries that have not been rejected by another plugin or failed from the queue.
        """
        for imdb_id, entry in self.accepted_entries.iteritems():
            if entry in feed.accepted and entry not in feed.failed:
                # If entry was not rejected or failed, remove from database
                item = feed.session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
                feed.session.delete(item)
                log.debug('%s was successful, removing from imdb-queue' % entry['title'])


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
        if not parser.rargs:
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

    def parse_what(self, what):
        """Given an imdb id or movie title, looks up from imdb and returns a dict with imdb_id and title keys"""
        imdb_id = extract_id(what)
        title = what

        if imdb_id:
            # Given an imdb id, find title
            parser = ImdbParser()
            try:
                parser.parse('http://www.imdb.com/title/%s' % imdb_id)
            except Exception:
                raise QueueError('Error parsing info from imdb for %s' % imdb_id)
            if parser.name:
                title = parser.name
        else:
            # Given a title, try to do imdb search for id
            print 'Searching imdb for %s' % what
            search = ImdbSearch()
            result = search.smart_match(what)
            if not result:
                raise QueueError('ERROR: Unable to find any such movie from imdb, use imdb url instead.')
            imdb_id = extract_id(result['url'])
            title = result['name']

        self.options['imdb_id'] = imdb_id
        self.options['title'] = title
        return {'title': title, 'imdb_id': imdb_id}

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
        if action != 'list':
            if not self.options.get('what'):
                self.error('No URL or NAME given')
                return
            else:
                # Generate imdb_id and movie title from movie name, or imdb_url
                try:
                    what = self.parse_what(self.options['what'])
                except QueueError, e:
                    print e.message
                else:
                    self.options.update(what)

            if not self.options.get('title') or not self.options.get('imdb_id'):
                print 'could not determine movie to add' # TODO: Rethink errors
                return

        from sqlalchemy.exceptions import OperationalError
        try:
            if action == 'add':
                try:
                    added = self.queue_add(title=self.options['title'], imdb_id=self.options['imdb_id'],
                               quality=self.options['quality'], force=self.options['force'])
                except QueueError, e:
                    print e.message
                    if e.errno == 1:
                        # This is an invalid quality error, display some more info
                        print 'Recognized qualities are %s' % ', '.join([qual.name for qual in qualities.all()])
                        print 'ANY is the default and can also be used explicitly to specify that quality should be ignored.'
                else:
                    print 'Added %s to queue with quality %s' % (added['title'], added['quality'])
            elif action == 'del':
                try:
                    title = self.queue_del(self.options['imdb_id'])
                except QueueError, e:
                    print e.message
                else:
                    print '%s removed from queue.' % title
            elif action == 'list':
                self.queue_list()
        except OperationalError:
            log.critical('OperationalError')

    def error(self, msg):
        print 'IMDb Queue error: %s' % msg

    def validate_quality(self, quality):
        # Check that the quality is valid
        # Make sure quality is in the format we expect
        if quality.upper() == 'ANY':
            return 'ANY'
        elif qualities.get(quality, False):
            return qualities.common_name(quality)
        else:
            raise QueueError('ERROR! Unknown quality `%s`' % quality, errno=1)

    def queue_add(self, title=None, imdb_id=None, quality='ANY', force=True):
        """Add an item to the queue with the specified quality"""

        if not title or not imdb_id:
            # We don't have all the info we need to add movie, do a lookup for more info
            result = self.parse_what(imdb_id or title)
            title = result['title']
            imdb_id = result['imdb_id']
        quality = self.validate_quality(quality)

        session = Session()

        # check if the item is already queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if not item:
            item = ImdbQueue(imdb_id, quality, force)
            item.title = title
            session.add(item)
            session.commit()
            return {'title': title, 'imdb_id': imdb_id, 'quality': quality, 'force': force}
        else:
            raise QueueError('ERROR: %s is already in the queue' % title)

    def queue_del(self, imdb_id):
        """Delete the given item from the queue"""

        session = Session()
        # check if the item is queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if item:
            title = item.title
            session.delete(item)
            session.commit()
            return title
        else:
            raise QueueError('%s is not in the queue' % imdb_id)

    def queue_edit(self, imdb_id, quality):
        """Change the required quality for a movie in the queue"""
        self.validate_quality(quality)
        session = Session()
        # check if the item is queued
        item = session.query(ImdbQueue).filter(ImdbQueue.imdb_id == imdb_id).first()
        if item:
            item.quality = quality
            session.commit()
            return item.title
        else:
            raise QueueError('%s is not in the queue' % imdb_id)

    def queue_list(self):
        """List IMDb queue"""

        items = self.queue_get()
        print '-' * 79
        print '%-10s %-45s %-8s %s' % ('IMDB id', 'Title', 'Quality', 'Force')
        print '-' * 79
        for item in items:
            print '%-10s %-45s %-8s %s' % (item.imdb_id, item.title, item.quality, item.immortal)

        if not items:
            print 'IMDB queue is empty'

        print '-' * 79

    def queue_get(self):
        """Get the current IMDb queue"""
        session = Session()
        items = session.query(ImdbQueue).all()
        for item in items:
            if not item.title:
                # old database does not have title / title not retrieved
                try:
                    item.title = self.parse_what(item.imdb_id)['title']
                except QueueError:
                    item.title = 'N/A'
        return items

register_plugin(FilterImdbQueue, 'imdb_queue')
register_plugin(ImdbQueueManager, 'imdb_queue_manager', builtin=True)
# Handle if a urlrewrite happens, need to get accurate quality.
register_feed_phase(FilterImdbQueue, 'imdbqueue', after='urlrewrite')

register_parser_option('--imdb-queue', action='callback', callback=ImdbQueueManager.optik_imdb_queue,
                       help='(add|del|list) [IMDB_URL|NAME] [QUALITY]')
