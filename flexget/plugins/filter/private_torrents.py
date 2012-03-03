import logging
from flexget.plugin import register_plugin, priority

log = logging.getLogger('priv_torrents')


class FilterPrivateTorrents(object):
    """How to handle private torrents.

    private_torrents: yes|no

    Example::

      private_torrents: no

    This would reject all torrent entries with private flag.

    Example::

      private_torrents: yes

    This would reject all public torrents.

    Non-torrent content is not interviened.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(127)
    def on_feed_modify(self, feed):
        private_torrents = feed.config['private_torrents']

        rejected = False
        for entry in feed.accepted:
            if not 'torrent' in entry:
                log.debug('`%s` is not a torrent' % entry['title'])
                continue
            private = entry['torrent'].private

            if not private_torrents and private:
                feed.reject(entry, 'torrent is marked as private', remember=True)
                rejected = True
            if private_torrents and not private:
                feed.reject(entry, 'public torrent', remember=True)
                rejected = True

register_plugin(FilterPrivateTorrents, 'private_torrents')
