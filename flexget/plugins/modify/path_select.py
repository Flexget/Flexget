from __future__ import unicode_literals, division, absolute_import
import logging
import os
import random
from collections import namedtuple

from flexget import plugin
from flexget.event import event
from flexget.config_schema import parse_size, parse_percent
from flexget.config_schema import one_or_more

log = logging.getLogger('path_select')


disk_stats_tuple = namedtuple(
    'disk_stats', [
        'path', 'free_bytes', 'used_bytes', 'total_bytes', 'free_percent',  'used_percent'
    ]
)


def os_disk_stats(folder):
    """ Return drive free, used and total bytes """
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

        return free_bytes.value, total_bytes.value
    else:
        stats = os.statvfs(folder)
        return stats.f_bavail * stats.f_frsize, stats.f_blocks * stats.f_frsize


def disk_stats(folder):

    free_bytes, total_bytes = os_disk_stats(folder)
    used_bytes = total_bytes - free_bytes
    free_percent = 0.0 if total_bytes == 0 else 100 * free_bytes / total_bytes
    used_percent = 0.0 if total_bytes == 0 else 100 * used_bytes / total_bytes

    return disk_stats_tuple(folder, free_bytes, used_bytes, total_bytes, free_percent, used_percent)


def _path_selector(paths, threshold, stat_attr, reverse=True):
    paths_stats = [disk_stats(path) for path in paths]

    # Sort paths by key
    paths_stats.sort(key=lambda p: getattr(p, stat_attr), reverse=reverse)

    valid_paths = [paths_stats[0].path]

    if threshold > 0:
        valid_paths.extend([
            path_stat.path for path_stat in paths_stats[1:]
            if abs(getattr(path_stat, stat_attr) - getattr(paths_stats[0], stat_attr)) <= threshold
        ])

    return random.choice(valid_paths)


def select_most_free(paths, threshold):
    return _path_selector(paths, threshold, 'free_bytes', reverse=True)


def select_most_used(paths, threshold):
    return _path_selector(paths, threshold, 'used_bytes', reverse=True)


def select_most_free_percent(paths, threshold):
    return _path_selector(paths, threshold, 'free_percent', reverse=True)


def select_most_used_percent(paths, threshold):
    return _path_selector(paths, threshold, 'used_percent', reverse=True)


def select_has_free(paths, threshold):
    paths_stats = [disk_stats(path) for path in paths]

    valid_paths = [
        path_stat.path for path_stat in paths_stats
        if path_stat.free_bytes >= threshold
    ]
    if valid_paths:
        return random.choice(valid_paths)


selector_map = {
    'most_free': select_most_free,
    'most_used': select_most_used,
    'most_free_percent': select_most_free_percent,
    'most_used_percent': select_most_used_percent,
    'has_free': select_has_free,
}


class PluginPathSelect(object):
    """Allows setting a field to a folder based on it's space

    Path will be selected at random if multiple paths match the threshold

    Example:

    path_select:
      select: most_free_percent # or most_free, most_used, most_used_percent, has_free
      threshold: 9000 # Threshold in MB or percent.
      paths:
        - /drive1/
        - /drive2/
        - /drive3/
    """

    schema = {
        'type': 'object',
        'properties': {
            'select': {'type': 'string', 'enum': selector_map.keys()},
            'to_field': {'type': 'string', 'default': 'path'},
            'paths': one_or_more({'type': 'string', 'format': 'path'}),
            'threshold': {
                'oneOf': [
                    {'type': 'string', 'format': 'size'},
                    {'type': 'string', 'format': 'percent'},
                ]
            },
        },
        'required': ['paths', 'select'],
        'additionalProperties': False,
    }

    @plugin.priority(250)  # run before other plugins
    def on_task_metainfo(self, task, config):

        selector = selector_map[config['select']]

        # Convert threshold to bytes (int) or percent (float)
        threshold = config.get('threshold')
        if isinstance(threshold, basestring) and '%' in threshold:
            threshold = parse_percent(threshold)
        else:
            threshold = parse_size(threshold)

        path = selector(config['paths'], threshold=threshold)

        if path:
            log.debug('Path %s selected due to (%s)' % (path, config['select']))

            for entry in task.all_entries:
                entry[config['to_field']] = path
        else:
            task.abort('Unable to select a path based on %s' % config['select'])
            return


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPathSelect, 'path_select', api_ver=2)
