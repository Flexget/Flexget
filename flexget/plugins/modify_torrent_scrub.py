""" Torrent Scrubber Plugin.
"""

import os
import logging
from flexget import plugin, validator
from flexget import feed as flexfeed
from flexget.utils import bittorrent 
from flexget.plugins import modify_torrent

# Global constants
NAME = __name__.split('.')[-1].split('_', 1)[1]
LOG = logging.getLogger(NAME)


class PluginTorrentScrubber(object):
    """ Scrubs torrents from unwanted keys.

        Example:
            feeds:
              rutorrent-fast-resume-infected-feed:
                rtorrent_scrub: resume
    """
    # Scrub at high level, but BELOW "torrent"
    SCRUB_PRIO = modify_torrent.TorrentFilename.TORRENT_PRIO - 10

    # Scrubbing modes
    SCRUB_MODES = ("off", "on", "all", "resume", "rtorrent",)

    # Keys of rTorrent / ruTorrent session data
    RT_KEYS = ("libtorrent_resume", "log_callback", "err_callback", "rtorrent")

    def validator(self):
        """ Our configuration model.
        """
        root = validator.factory()
        root.accept("boolean")
        root.accept("choice").accept_choices(self.SCRUB_MODES, ignore_case=True)
        return root

    @plugin.priority(SCRUB_PRIO)
    def on_feed_modify(self, feed, config):
        """ Scrub items that are torrents, if they're affected.
        """
        mode = str(config).lower()
        if mode in ("off", "false"):
            LOG.debug("Plugin configured, but disabled")
            return

        for entry in feed.entries:
            # Skip non-torrents
            if "torrent" not in entry:
                continue

            # Scrub keys as configured            
            modified = False
            metainfo = entry["torrent"].content
            infohash = entry["torrent"].get_info_hash()

            if mode in ("on", "all", "true"):
                modified = bittorrent.clean_meta(metainfo, including_info=(mode == "all"), logger=LOG)
            elif mode in ("resume", "rtorrent"):
                if mode == "resume":
                    self.RT_KEYS = self.RT_KEYS[:1]

                for key in self.RT_KEYS:
                    if key in metainfo:
                        LOG.info("Removing key %r..." % (key,))
                        del metainfo[key]
                        modified = True
            else:
                raise ValueError("INTERNAL ERROR: Unknown mode %r" % mode)

            # Commit any changes back into entry
            if modified:
                entry["torrent"].content = metainfo
                entry["torrent"].modified = True
                LOG.info("Torrent '%s' was scrubbed!" % entry['title'])
                new_infohash = entry["torrent"].get_info_hash()
                if infohash != new_infohash:
                    LOG.warn("Info hash changed from #%s to #%s in %s" % (infohash, new_infohash, entry['filename']))
                

plugin.register_plugin(PluginTorrentScrubber, NAME, api_ver=2)
