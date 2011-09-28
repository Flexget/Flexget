import logging
from urllib import quote
from urllib2 import URLError
from flexget.utils.tools import urlopener
from flexget.utils.bittorrent import bdecode
from flexget.plugin import register_plugin

log = logging.getLogger('torrent_alive')


class TorrentAlive(object):

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_modify(self, feed, config):
        if not config:
            return
        for entry in feed.accepted:
            torrent = entry.get('torrent')
            if torrent:
                seeds = None
                info_hash = torrent.get_info_hash()
                announce_list = torrent.content.get('announce-list')
                if announce_list:
                    # Multitracker torrent
                    for tier in announce_list:
                        for tracker in tier:
                            try:
                                seeds = self.get_tracker_seeds(tracker, info_hash)
                            except URLError, e:
                                log.debug('Error scraping %s: %s' % (tracker, e))
                                # Error connecting to tracker, try the next in this tier
                                continue
                            else:
                                # If we successfully connect to a tracker in this tier, no need to try the others
                                break
                        if seeds:
                            # If we already found a tracker with seeds, no need to continue
                            break
                else:
                    # Single tracker
                    tracker = torrent.content['announce']
                    try:
                        seeds = self.get_tracker_seeds(tracker, info_hash)
                    except URLError, e:
                        log.debug('Error scraping %s: %s' % (tracker, e))
                if not seeds:
                    feed.reject(entry, reason='Tracker(s) did not have any seeds.', remember_time='1 hour')
                    feed.rerun()
                else:
                    log.debug('Found %i seeds from %s' % (seeds, tracker))

    def get_scrape_url(self, tracker_url):
        if tracker_url.endswith('announce'):
            result = tracker_url.replace('announce', 'scrape')
            if result.startswith('udp'):
                result = result.replace('udp', 'http')
            return result
        else:
            log.debug('Cannot determine scrape url for %s' % tracker_url)

    def get_tracker_seeds(self, url, info_hash):
        url = self.get_scrape_url(url)
        if not url:
            return
        log.debug('Checking for seeds from %s' % url)
        url += '?info_hash=%s' % quote(info_hash.decode('hex'))
        data = urlopener(url, log, retries=2)
        return bdecode(data.read())['files'].values()[0]['complete']


register_plugin(TorrentAlive, 'torrent_alive', api_ver=2)
