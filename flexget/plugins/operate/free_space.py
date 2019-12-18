import os

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='free_space')


def get_free_space(folder):
    """ Return folder/drive free space (in megabytes)"""
    if os.name == 'nt':
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes)
        )
        return free_bytes.value / (1024 * 1024)
    else:
        stats = os.statvfs(folder)
        return (stats.f_bavail * stats.f_frsize) / (1024 * 1024)


class PluginFreeSpace:
    """Aborts a task if an entry is accepted and there is less than a certain amount of space free on a drive."""

    schema = {
        'oneOf': [
            {'type': 'number'},
            {
                'type': 'object',
                'properties': {
                    'space': {'type': 'number'},
                    'path': {'type': 'string', 'format': 'path'},
                },
                'required': ['space'],
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config, task):
        if isinstance(config, (float, int)):
            config = {'space': config}
        # Use config path if none is specified
        if not config.get('path'):
            config['path'] = task.manager.config_base
        return config

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        # Only bother aborting if there were accepted entries this run.
        if task.accepted:
            if get_free_space(config['path']) < config['space']:
                logger.error(
                    'Less than {} MB of free space in {} aborting task.',
                    config['space'],
                    config['path'],
                )
                # backlog plugin will save and restore the task content, if available
                task.abort('Less than {} MB of free space in {}', config['space'], config['path'])


@event('plugin.register')
def register_plugin():
    plugin.register(PluginFreeSpace, 'free_space', api_ver=2)
