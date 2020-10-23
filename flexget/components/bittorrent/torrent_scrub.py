from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils import bittorrent

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.bittorrent import torrent as plugin_torrent
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='torrent')

logger = logger.bind(name='torrent_scrub')


class TorrentScrub:
    """ Scrubs torrents from unwanted keys.

        Example:
            tasks:
              rutorrent-fast-resume-infected-task:
                torrent_scrub: resume
    """

    # Scrub at high level, but BELOW "torrent"
    SCRUB_PRIO = plugin_torrent.TorrentFilename.TORRENT_PRIO - 10

    # Scrubbing modes
    SCRUB_MODES = ("off", "on", "all", "resume", "rtorrent")

    # Keys of rTorrent / ruTorrent session data
    RT_KEYS = ("libtorrent_resume", "log_callback", "err_callback", "rtorrent")

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'string', 'enum': list(SCRUB_MODES)},
            {'type': 'array', 'items': {'type': 'string'}},  # list of keys to scrub
        ]
    }

    @plugin.priority(SCRUB_PRIO)
    def on_task_modify(self, task, config):
        """ Scrub items that are torrents, if they're affected.
        """
        if isinstance(config, list):
            mode = "fields"
        else:
            mode = str(config).lower()
            if mode in ("off", "false"):
                logger.debug("Plugin configured, but disabled")
                return

        for entry in task.entries:
            # Skip non-torrents
            if "torrent" not in entry:
                continue

            # Scrub keys as configured
            modified = set()
            metainfo = entry["torrent"].content
            infohash = entry["torrent"].info_hash

            if mode in ("on", "all", "true"):
                modified = bittorrent.clean_meta(
                    metainfo, including_info=(mode == "all"), log_func=logger.debug
                )
            elif mode in ("resume", "rtorrent"):
                if mode == "resume":
                    self.RT_KEYS = self.RT_KEYS[:1]

                for key in self.RT_KEYS:
                    if key in metainfo:
                        logger.debug("Removing key '{}'...", key)
                        del metainfo[key]
                        modified.add(key)
            elif mode == "fields":
                # Scrub all configured fields
                for key in config:
                    fieldname = key  # store for logging
                    key = bittorrent.Torrent.KEY_TYPE(key)
                    field = metainfo

                    while field and '.' in key:
                        name, key = key.split('.', 1)
                        try:
                            field = field[name]
                        except KeyError:
                            # Key not found in this entry
                            field = None
                        logger.trace((key, field))

                    if field and key in field:
                        logger.debug("Removing key '{}'...", fieldname)
                        del field[key]
                        modified.add(fieldname)
            else:
                raise ValueError("INTERNAL ERROR: Unknown mode %r" % mode)

            # Commit any changes back into entry
            if modified:
                entry["torrent"].content = metainfo
                entry["torrent"].modified = True
                logger.info(
                    ('Key {} was' if len(modified) == 1 else 'Keys {} were')
                    + " scrubbed from torrent '{}'!",
                    ', '.join(sorted(modified)),
                    entry['title'],
                )
                new_infohash = entry["torrent"].info_hash
                if infohash != new_infohash:
                    logger.warning(
                        "Info hash changed from #{} to #{} in '{}'",
                        infohash,
                        new_infohash,
                        entry['filename'],
                    )


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentScrub, interfaces=['task', 'torrent'], api_ver=2)
