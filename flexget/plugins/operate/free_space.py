import logging
import os
from flexget.plugin import register_plugin, priority

log = logging.getLogger('free_space')


def get_free_space(folder):
    """ Return folder/drive free space (in megabytes)"""
    if os.name == 'nt':
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / (1024 * 1024)
    else:
        stats = os.statvfs(folder)
        return (stats.f_bavail * stats.f_frsize) / (1024 * 1024)


class PluginFreeSpace(object):
    """Aborts a feed if an entry is accepted and there is less than a certain amount of space free on a drive."""

    def validator(self):
        from flexget import validator
        root = validator.factory()
        # Allow just the free space at the root
        root.accept('number')
        # Also allow a dict with path and free space
        advanced = root.accept('dict')
        advanced.accept('number', key='space', required=True)
        advanced.accept('path', key='path')
        return root

    def get_config(self, feed):
        config = feed.config.get('free_space', {})
        if isinstance(config, (float, int)):
            config = {'space': config}
        # Use config path if none is specified
        if not config.get('path'):
            config['path'] = feed.manager.config_base
        return config

    @priority(255)
    def on_feed_download(self, feed):
        config = self.get_config(feed)
        # Only bother aborting if there were accepted entries this run.
        if feed.accepted:
            if get_free_space(config['path']) < config['space']:
                log.error('Less than %d MB of free space in %s aborting feed.' % (config['space'], config['path']))
                # backlog plugin will save and restore the feed content, if available
                feed.abort()


register_plugin(PluginFreeSpace, 'free_space')
