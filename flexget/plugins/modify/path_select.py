from __future__ import unicode_literals, division, absolute_import
import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('path_select')


def percentage(part, whole):
    try:
        return 100 * float(part)/float(whole)
    except ZeroDivisionError:
        return float(0.0)


def get_disk_stats(folder):
    """ Return folder/drive stats in megabytes (free, used, total) """
    if os.name == 'nt':
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(folder),
            None,
            ctypes.pointer(total_bytes),
            ctypes.pointer(free_bytes)
        )

        free_bytes = free_bytes.value
        total_bytes = total_bytes.value
    else:
        stats = os.statvfs(folder)
        free_bytes = stats.f_bavail * stats.f_frsize
        total_bytes = stats.f_blocks * stats.f_frsize

    free_bytes_mb = int(free_bytes / 1024 / 1024)
    total_bytes_mb = int(total_bytes / 1024 / 1024)
    used_bytes_mb = total_bytes_mb - free_bytes_mb

    return free_bytes_mb, used_bytes_mb, total_bytes_mb


def get_free_space(folder):
    return get_disk_stats(folder)[0]


def get_used_space(folder):
    return get_disk_stats(folder)[1]


def get_free_space_percent(folder):
    free_bytes_mb, __, total_bytes_mb = get_disk_stats(folder)
    return percentage(free_bytes_mb, total_bytes_mb)


def get_used_space_percent(folder):
    __, used_bytes_mb, total_bytes_mb = get_disk_stats(folder)
    return percentage(used_bytes_mb, total_bytes_mb)


def select_most_free(paths, reverse=False):
    return sorted(paths, key=get_free_space, reverse=not reverse)[0]


def select_most_free_percent(paths, reverse=False):
    return sorted(paths, key=get_free_space_percent, reverse=not reverse)[0]


def select_most_used(paths, reverse=True):
    return sorted(paths, key=get_used_space, reverse=not reverse)[0]


def select_most_used_percent(paths, reverse=True):
    return sorted(paths, key=get_used_space_percent, reverse=not reverse)[0]


selector_map = {
    "most_free": select_most_free,
    "most_used": select_most_used,
    "most_free_percent": select_most_free_percent,
    "most_used_percent": select_most_used_percent,
}


class PluginPathSelect(object):
    """Allows setting a field to a folder based on it's space

    Example:

    path_select:
      select: most_free_percent # or most_free, most_used, most_used_percent
      reverse: False # reverse the select, default is False
      paths:
        - /drive1/
        - /drive2/
        - /drive3/
    """

    schema = {
        'type': 'object',
        'properties': {
            'select': {'type': 'string', 'enum': selector_map.keys()},
            'reverse': {'type': 'boolean'},
            'to_field': {'type': 'string'},
            'paths': one_or_more({'type': 'string'})
        },
        'required': ['paths', 'select'],
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        config.setdefault('to_field', "path")
        config.setdefault('reverse', False)
        return config

    @plugin.priority(250)  # run before other plugins
    def on_task_metainfo(self, task, config):
        config = self.prepare_config(config)

        if not config.get('paths'):
            return

        selector = selector_map[config['select']]
        path = selector(config['paths'], reverse=config['reverse'])
        log.debug("path %s selected due to (%s)" % (path, config['select']))

        for entry in task.all_entries:
            entry[config['to_field']] = path


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPathSelect, 'path_select', api_ver=2)
