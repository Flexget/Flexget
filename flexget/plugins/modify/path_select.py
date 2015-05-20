from __future__ import unicode_literals, division, absolute_import
import logging
import os
import random
from collections import namedtuple

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('path_select')

SYMBOLS = {
    'customary': ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y'),
    'customary_ext': ('byte', 'kilo', 'mega', 'giga', 'tera', 'peta', 'exa', 'zetta', 'iotta'),
    'iec': ('Bi', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi'),
    'iec_ext': ('byte', 'kibi', 'mebi', 'gibi', 'tebi', 'pebi', 'exbi', 'zebi', 'yobi'),
}


def human2bytes(s):
    """
    Attempts to guess the string format based on default symbols
    set and return the corresponding bytes as an integer.
    When unable to recognize the format ValueError is raised.
    """

    init = s
    num = ""
    while s and s[0:1].isdigit() or s[0:1] == '.':
        num += s[0]
        s = s[1:]
    num = float(num)
    letter = s.strip()
    for name, sset in SYMBOLS.items():
        if letter in sset:
            break
    else:
        if letter == 'k':
            # treat 'k' as an alias for 'K' as per: http://goo.gl/kTQMs
            sset = SYMBOLS['customary']
            letter = letter.upper()
        else:
            raise ValueError("can't interpret %r" % init)
    prefix = {sset[0]: 1}
    for i, s in enumerate(sset[1:]):
        prefix[s] = 1 << (i+1)*10
    return int(num * prefix[letter])


def percentage(part, whole):
    try:
        return 100 * part/whole
    except ZeroDivisionError:
        return 0.0


disk_stats_tuple = namedtuple(
    'disk_stats', [
        'path', 'free_bytes', 'used_bytes', 'total_bytes', 'free_percent',  'used_percent'
    ]
)


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

    free_bytes = int(free_bytes)
    total_bytes = int(total_bytes)
    used_bytes = total_bytes - free_bytes

    free_percent = 0.0 if total_bytes == 0 else percentage(free_bytes, total_bytes)
    used_percent = 0.0 if total_bytes == 0 else percentage(used_bytes, total_bytes)

    return disk_stats_tuple(folder, free_bytes, used_bytes, total_bytes, free_percent, used_percent)


def path_selector(paths, threshold, stat_attr, reverse=True):
    paths_stats = [get_disk_stats(path) for path in paths]

    # Sort paths by key
    paths_stats.sort(key=lambda p: getattr(p, stat_attr), reverse=reverse)

    valid_paths = [paths_stats[0].path]

    if isinstance(threshold, float):
        # Percentage
        valid_paths.extend([
            path_stat.path for path_stat in paths_stats[1:]
            if abs(getattr(path_stat, stat_attr) - getattr(paths_stats[0], stat_attr)) <= threshold
        ])

    elif isinstance(threshold, int) and threshold > 0:
        # Size in bytes
        valid_paths.extend([
            path_stat.path for path_stat in paths_stats[1:]
            if abs(getattr(path_stat, stat_attr) - getattr(paths_stats[0], stat_attr)) <= threshold
        ])

    return random.choice(valid_paths)


def select_most_free(paths, threshold):
    return path_selector(paths, threshold, "free_bytes", reverse=True)


def select_most_used(paths, threshold):
    return path_selector(paths, threshold, "used_bytes", reverse=True)


def select_most_free_percent(paths, threshold):
    return path_selector(paths, threshold, "free_percent", reverse=True)


def select_most_used_percent(paths, threshold):
    return path_selector(paths, threshold, "used_percent", reverse=True)


def select_has_free(paths, threshold):
    paths_stats = [get_disk_stats(path) for path in paths]

    valid_paths = [
        path_stat.path for path_stat in paths_stats
        if path_stat.free_bytes >= threshold
    ]

    if valid_paths:
        return random.choice(valid_paths)


selector_map = {
    "most_free": select_most_free,
    "most_used": select_most_used,
    "most_free_percent": select_most_free_percent,
    "most_used_percent": select_most_used_percent,
    "has_free": select_has_free,
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
            'threshold': {'type': 'string', 'default': "0%", 'pattern': '^\d+\s?(%|[BKMGT]?)$'},
            'to_field': {'type': 'string', 'default': 'path'},
            'paths': one_or_more({'type': 'string', 'format': 'path'})
        },
        'required': ['paths', 'select'],
        'additionalProperties': False,
    }

    @plugin.priority(250)  # run before other plugins
    def on_task_metainfo(self, task, config):

        selector = selector_map[config['select']]

        # Convert threshold to bytes (int) or percent (float)
        if '%' in config['threshold']:
            try:
                threshold = float(config['threshold'].strip('%'))
            except ValueError:
                raise plugin.PluginError("%s is not a valid percentage" % config['threshold'])
        else:
            try:
                threshold = human2bytes(config['threshold'])
            except ValueError as e:
                raise plugin.PluginError("%s is not a valid size" % config['threshold'])

        path = selector(config['paths'], threshold=threshold)

        if path:
            log.debug("Path %s selected due to (%s)" % (path, config['select']))

            for entry in task.all_entries:
                entry[config['to_field']] = path
        else:
            log.warning("Unable to select a path based on %s" % config['select'])
            return


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPathSelect, 'path_select', api_ver=2)
