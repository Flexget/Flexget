import logging
from urllib import quote
from urllib2 import URLError
from flexget.utils.tools import urlopener
from flexget.utils.bittorrent import bdecode
from flexget.plugin import register_plugin, priority

log = logging.getLogger('torrent_alive')


class TorrentAlive(object):

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('integer')
        return root

    @priority(150)
    def on_feed_filter(self, feed, config):
        if not config:
            return
        for entry in feed.entries:
            if 'torrent_seeds' in entry and entry['torrent_seeds'] < config:
                feed.reject(entry, reason='Had < %d required seeds. (%s)' % (config, entry['torrent_seeds']))

    # Run on output phase so that we let torrent plugin output modified torrent file first
    @priority(250)
    def on_feed_output(self, feed, config):
        if not config:
            return
        # Convert True to 1
        min_seeds = int(config)
        for entry in feed.accepted:
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
                    for tier in announce_list:
                        for tracker in tier:
                            try:
                                tracker_seeds = self.get_tracker_seeds(tracker, info_hash)
                            except URLError, e:
                                log.debug('Error scraping %s: %s' % (tracker, e))
                                # Error connecting to tracker, try the next in this tier
                                continue
                            else:
                                log.debug('%s seeds found from %s' % (tracker_seeds, tracker))
                                # The same peer may be connected to multiple trackers, so just use the max seeds
                                # found by any one tracker.
                                seeds = max(seeds, tracker_seeds)
                                # If we successfully connect to a tracker in this tier, no need to try the others
                                break
                        if seeds >= min_seeds:
                            # If we already found enough seeds, no need to continue
                            break
                else:
                    # Single tracker
                    tracker = torrent.content['announce']
                    try:
                        seeds = self.get_tracker_seeds(tracker, info_hash)
                    except URLError, e:
                        log.debug('Error scraping %s: %s' % (tracker, e))
                if seeds < min_seeds:
                    feed.reject(entry, reason='Tracker(s) had < %s required seeds. (%s)' % (min_seeds, seeds),
                                remember_time='1 hour')
                    feed.rerun()
                else:
                    log.debug('Found %i seeds from trackers' % seeds)

    def get_scrape_url(self, tracker_url, info_hash):
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

    def get_tracker_seeds(self, url, info_hash):
        url = self.get_scrape_url(url, info_hash)
        if not url:
            return 0
        log.debug('Checking for seeds from %s' % url)
        try:
            data = bdecode(urlopener(url, log, retries=1, timeout=10).read()).get('files')
        except SyntaxError, e:
            log.warning('Error bdecoding tracker response: %s' % e)
            return 0
        if not data:
            return 0
        return data.values()[0]['complete']


register_plugin(TorrentAlive, 'torrent_alive', api_ver=2)
