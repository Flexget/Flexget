import os

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='free_space')


def get_free_space(config, task):
    """Return folder/drive free space (in megabytes)"""
    if 'host' in config:
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                config['host'],
                config['port'],
                config['user'],
                config['ssh_key_filepath'],
                timeout=5000,
            )
        except Exception as e:
            logger.error("Issue connecting to remote host. {}", e)
            task.abort('Error with remote host.')
        if config['allotment'] != -1:
            stdin, stdout, stderr = ssh.exec_command(f"du -s {config['path']} | cut -f 1")
        else:
            stdin, stdout, stderr = ssh.exec_command(
                f"df -k {config['path']} | tail -1 | tr -s ' ' | cut -d' ' -f4"
            )
        outlines = stdout.readlines()
        resp = ''.join(outlines)
        ssh.close()
        try:
            if config['allotment'] != -1:
                free = int(config['allotment']) - ((int(resp.strip()) * 1024) / 1000000)
            else:
                free = int(resp.strip()) / 1000
        except ValueError:
            logger.error('Non-integer was returned when calculating disk usage.')
            task.abort('Error with remote host.')
        return free
    elif os.name == 'nt':
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(config['path']), None, None, ctypes.pointer(free_bytes)
        )
        return free_bytes.value / (1024 * 1024)
    else:
        stats = os.statvfs(config['path'])
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
                    'path': {'type': 'string'},
                    'port': {'type': 'integer', 'default': 22},
                    'host': {'type': 'string'},
                    'user': {'type': 'string'},
                    'ssh_key_filepath': {'type': 'string'},
                    'allotment': {'type': 'number', 'default': -1},
                    'when': one_or_more(
                        {'type': 'string', 'enum': ['start', 'filter', 'download']}
                    ),
                    'action': {
                        'type': 'string',
                        'enum': ['abort', 'reject', 'accept', 'fail'],
                        'default': 'abort',
                    },
                },
                'required': ['space'],
                'dependencies': {'host': ['user', 'ssh_key_filepath', 'path']},
                'additionalProperties': False,
            },
        ]
    }

    @staticmethod
    def entry_task_handle(task, action):
        for entry in task.entries:
            if action == 'accept':
                entry.accept()
            elif action == 'reject':
                entry.reject()
            elif action == 'fail':
                entry.fail()

    @staticmethod
    def prepare_config(config, task):
        if isinstance(config, (float, int)):
            config = {'space': config}
        # Use config path if none is specified
        if not config.get('path'):
            config['path'] = task.manager.config_base
        if not config.get('action'):
            config['action'] = 'abort'

        if not config.get('when'):
            config['when'] = ['download']
        elif not isinstance(config['when'], list):
            config['when'] = [config['when']]

        return config

    def run_phase(self, task, config):
        config = self.prepare_config(config, task)

        if not task.current_phase in config['when']:
            return

        action = config['action']

        free_space = get_free_space(config, task)
        space = config['space']
        path = config['path']
        if free_space < space:

            # backlog plugin will save and restore the task content, if available
            if action == 'abort':
                logger.error('Less than {} MB of free space in {} aborting task.', space, path)
                task.abort(f"Less than {space} MB of free space in {path}")
            else:
                logger.debug(
                    'Less than {} MB of free space in {}! {} all entries.',
                    space,
                    path,
                    action.capitalize(),
                )
                self.entry_task_handle(task, action)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        config = self.prepare_config(config, task)
        action = config['action']

        # Only bother run in action in abort.
        if action != 'abort':
            return

        self.run_phase(task, config)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        self.run_phase(task, config)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        action = config['action']

        # Only bother aborting in download if there were accepted entries this run.
        if not task.accepted and action == 'abort':
            return

        self.run_phase(task, config)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginFreeSpace, 'free_space', api_ver=2)
