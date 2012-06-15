import logging
import threading
from httplib import BadStatusLine
from urllib import quote
from urllib2 import URLError
from flexget.utils.tools import urlopener
from flexget.utils.bittorrent import bdecode
from flexget.plugin import register_plugin, priority

log = logging.getLogger('torrent_alive')


class TorrentAliveThread(threading.Thread):

    def __init__(self, tracker, info_hash):
        threading.Thread.__init__(self)
        self.tracker = tracker
        self.info_hash = info_hash
        self.tracker_seeds = 0

    def run(self):
        try:
            self.tracker_seeds = get_tracker_seeds(self.tracker, self.info_hash)
        except URLError, e:
            log.debug('Error scraping %s: %s' % (self.tracker, e))
            self.tracker_seeds = 0
        else:
            log.debug('%s seeds found from %s' % (self.tracker_seeds, get_scrape_url(self.tracker, self.info_hash)))


def max_seeds_from_threads(threads):
    """
    Joins the threads and returns the maximum seeds found from any of them.

    :param threads: A list of started `TorrentAliveThread`s
    :return: Maximum seeds found from any of the threads
    """
    seeds = 0
    for background in threads:
        log.debug('Coming up next: %s' % background.tracker)
        background.join()
        seeds = max(seeds, background.tracker_seeds)
        log.debug('Current hightest number of seeds found: %s' % seeds)
    return seeds


def get_scrape_url(tracker_url, info_hash):
    if 'announce' in tracker_url:
        result = tracker_url.replace('announce', 'scrape')
    else:
        log.debug('`announce` not contained in tracker url, guessing scrape address.')
        result = tracker_url + '/scrape'
    if result.startswith('udp:'):
        result = result.replace('udp:', 'http:')
    result += '&' if '?' in result else '?'
    result += 'info_hash=%s' % quote(info_hash.decode('hex'))
    return result


def get_tracker_seeds(url, info_hash):
    url = get_scrape_url(url, info_hash)
    if not url:
        log.debug('if not url is true returning 0')
        return 0
    log.debug('Checking for seeds from %s' % url)
    data = None
    try:
        data = bdecode(urlopener(url, log, retries=1, timeout=10).read()).get('files')
    except SyntaxError, e:
        log.warning('Error decoding tracker response: %s' % e)
        return 0
    except BadStatusLine, e:
        log.warning('Error BadStatusLine: %s' % e)
        return 0
    except IOError, e:
        log.warning('Server error: %s' % e)
        return 0
    if not data:
        log.debug('the moose is loose')
        return 0
    log.debug('get_tracker_seeds is returning: %s' % data.values()[0]['complete'])
    return data.values()[0]['complete']


class TorrentAlive(object):

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('integer')
        advanced = root.accept('dict')
        advanced.accept('integer', key='min_seeds')
        advanced.accept('interval', key='reject_for')
        return root

    def prepare_config(self, config):
        # Convert config to dict form
        if not isinstance(config, dict):
            config = {'min_seeds': int(config)}
        # Set the defaults
        config.setdefault('min_seeds', 1)
        config.setdefault('reject_for', '1 hour')
        return config

    @priority(150)
    def on_feed_filter(self, feed, config):
        if not config:
            return
        config = self.prepare_config(config)
        for entry in feed.entries:
            if 'torrent_seeds' in entry and entry['torrent_seeds'] < config['min_seeds']:
                feed.reject(entry, reason='Had < %d required seeds. (%s)' %
                                          (config['min_seeds'], entry['torrent_seeds']))

    # Run on output phase so that we let torrent plugin output modified torrent file first
    @priority(250)
    def on_feed_output(self, feed, config):
        if not config:
            return
        config = self.prepare_config(config)
        min_seeds = config['min_seeds']

        for entry in feed.accepted:
            # TODO: shouldn't this still check min_seeds ?
            if entry.get('torrent_seeds'):
                log.debug('Not checking trackers for seeds, as torrent_seeds is already filled.')
                continue
            log.debug('Checking for seeds for %s:' % entry['title'])
            torrent = entry.get('torrent')
            if torrent:
                seeds = 0
                info_hash = torrent.get_info_hash()
                announce_list = torrent.content.get('announce-list')
                if announce_list:
                    # Multitracker torrent
                    threadlist = []
                    for tier in announce_list:
                        for tracker in tier:
                            background = TorrentAliveThread(tracker, info_hash)
                            try:
                                background.start()
                                threadlist.append(background)
                            except threading.ThreadError:
                                # If we can't start a new thread, wait for current ones to complete and continue
                                log.debug('Reached max threads, finishing current threads.')
                                seeds = max(seeds, max_seeds_from_threads(threadlist))
                                background.start()
                                threadlist = [background]
                            log.debug('Started thread to scrape %s with info hash %s' % (tracker, info_hash))

                    seeds = max(seeds, max_seeds_from_threads(threadlist))
                    log.debug('Highest number of seeds found: %s' % seeds)
                else:
                    # Single tracker
                    tracker = torrent.content['announce']
                    try:
                        seeds = get_tracker_seeds(tracker, info_hash)
                    except URLError, e:
                        log.debug('Error scraping %s: %s' % (tracker, e))

                # Reject if needed
                if seeds < min_seeds:
                    feed.reject(entry, reason='Tracker(s) had < %s required seeds. (%s)' % (min_seeds, seeds),
                        remember_time=config['reject_for'])
                    feed.rerun()
                else:
                    log.debug('Found %i seeds from trackers' % seeds)

register_plugin(TorrentAlive, 'torrent_alive', api_ver=2)
