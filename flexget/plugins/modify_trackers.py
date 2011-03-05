import re
import logging
from flexget.plugin import *

log = logging.getLogger('modify_trackers')


class AddTrackers(object):

    """
        Adds tracker URL to torrent files.

        Configuration example:

        add_trackers:
          - uri://tracker_address:port/

        This will add all tracker URL uri://tracker_address:port/.
        TIP: You can use global section in configuration to make this enabled on all feeds.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('url', protocols=['udp', 'http'])
        return trackers

    @priority(127)
    def on_feed_modify(self, feed, config):
        for entry in feed.entries:
            if 'torrent' in entry:
                for url in config:
                    if not url in entry['torrent'].get_multitrackers():
                        entry['torrent'].add_multitracker(url)
                        log.info('Added %s tracker to %s' % (url, entry['title']))
            if entry['url'].startswith('magnet:'):
                entry['url'] += ''.join(['&tr=' + url for url in config])


class RemoveTrackers(object):

    """
        Removes trackers from torrent files using regexp matching.

        Configuration example:

        remove_trackers:
          - moviex

        This will remove all trackers that contain text moviex in their url.
        TIP: You can use global section in configuration to make this enabled on all feeds.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('regexp')
        return trackers

    @priority(127)
    def on_feed_modify(self, feed, config):
        for entry in feed.entries:
            if 'torrent' in entry:
                trackers = entry['torrent'].get_multitrackers()
                for tracker in trackers:
                    for regexp in config or []:
                        if re.search(regexp, tracker, re.IGNORECASE | re.UNICODE):
                            log.debug('remove_trackers removing %s because of %s' % (tracker, regexp))
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            log.info('Removed %s' % tracker)
            if entry['url'].startswith('magnet:'):
                for regexp in config:
                    # Replace any tracker strings that match the regexp with nothing
                    tr_search = r'&tr=([^&]*%s[^&]*)' % regexp
                    entry['url'] = re.sub(tr_search, '', entry['url'], re.IGNORECASE | re.UNICODE)

register_plugin(AddTrackers, 'add_trackers', api_ver=2)
register_plugin(RemoveTrackers, 'remove_trackers', api_ver=2)
