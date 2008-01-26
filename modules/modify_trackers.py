import yaml
import re
import logging

log = logging.getLogger('remove_trackers')

class RemoveTrackers:

    """
        Removes trackers from torrent files using regexp matching.

        Configuration example:

        remove_trackers:
          - .*moviex.*

        This will remove all trackers that contain text moviex in their url.
        TIP: You can use global section in configuration to make this enabled on all feeds.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="modify", keyword="remove_trackers", callback=self.remove)

    def remove(self, feed):
        for entry in feed.entries:
            if entry.has_key('torrent'):
                trackers = entry['torrent'].get_multitrackers()
                for tracker in trackers:
                    for regexp in feed.config.get('remove_trackers', []):
                        if re.search(regexp, tracker, re.IGNORECASE|re.UNICODE):
                            log.debug('remove_trackers removing %s because of %s' % (tracker, regexp))
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            # re-encode torrent data (file modified)
                            entry['data'] = entry['torrent'].encode()
