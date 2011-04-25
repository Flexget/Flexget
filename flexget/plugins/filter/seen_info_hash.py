from flexget.plugin import register_plugin, priority
from flexget.plugins.filter.seen import FilterSeen


class FilterSeenInfoHash(FilterSeen):
    """Prevents the same torrent from being downloaded twice by remembering the infohash of all downloaded torrents."""

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['torrent_info_hash']
        self.keyword = 'seen_info_hash'

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(180)
    def on_feed_filter(self, feed, config):
        # Return if we are disabled.
        if config is False:
            return
        # First make sure all the torrent_info_hash fields are in upper case
        for entry in feed.entries:
            if isinstance(entry.get('torrent_info_hash'), basestring):
                entry['torrent_info_hash'] = entry['torrent_info_hash'].upper()
        FilterSeen.on_feed_filter(self, feed, config, remember_rejected=True)

    def on_feed_modify(self, feed, config):
        # Return if we are disabled.
        if config is False:
            return
        # Run the filter again after the torrent plugin has populated the infohash
        self.on_feed_filter(feed, config)
        # Make sure no duplicates were accepted this run
        accepted_infohashes = set()
        for entry in feed.accepted:
            if 'torrent_info_hash' in entry:
                infohash = entry['torrent_info_hash']
                if infohash in accepted_infohashes:
                    feed.reject(entry, 'Already accepted torrent with this infohash once for this feed')
                else:
                    accepted_infohashes.add(infohash)

register_plugin(FilterSeenInfoHash, 'seen_info_hash', builtin=True, api_ver=2)
