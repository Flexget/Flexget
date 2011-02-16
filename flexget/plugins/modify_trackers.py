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
    def on_feed_modify(self, feed):
        trackers = feed.config['add_trackers']
        for entry in feed.entries:
            if 'torrent' in entry:
                for url in trackers:
                    if not url in entry['torrent'].get_multitrackers():
                        entry['torrent'].add_multitracker(url)
                        log.info('Added %s tracker to %s' % (url, entry['title']))


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
    def on_feed_modify(self, feed):
        for entry in feed.entries:
            if 'torrent' in entry:
                trackers = entry['torrent'].get_multitrackers()
                for tracker in trackers:
                    for regexp in feed.config.get('remove_trackers', []):
                        if re.search(regexp, tracker, re.IGNORECASE | re.UNICODE):
                            log.debug('remove_trackers removing %s because of %s' % (tracker, regexp))
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            log.info('Removed %s' % tracker)

register_plugin(AddTrackers, 'add_trackers')
register_plugin(RemoveTrackers, 'remove_trackers')
