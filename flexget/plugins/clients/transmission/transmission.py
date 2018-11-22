from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

from flexget.config_schema import one_or_more

from flexget.plugins.clients.transmission.utils import prepare_config, check_requirements
from flexget.plugins.clients.transmission.client import create_rpc_client, add_to_transmission

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass

log = logging.getLogger('transmission')


class TransmissionBase(object):
    def on_task_start(self, task, config):
        check_requirements()

        config = prepare_config(config)
        if config['enabled']:
            if task.options.test:
                log.info('Trying to connect to transmission...')
                create_rpc_client(config)


class PluginTransmission(TransmissionBase):
    """
    Add url from entry url to transmission

    Example::

      transmission:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location

    Default values for the config elements::

      transmission:
        host: localhost
        port: 9091
        enabled: yes
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string', 'default': 'localhost'},
                    'port': {'type': 'integer', 'default': 9091},
                    'netrc': {'type': 'string', 'default': None},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'enabled': {'type': 'boolean', 'default': True},
                    'path': {'type': 'string', 'default': ''},
                    'maxupspeed': {'type': 'number'},
                    'maxdownspeed': {'type': 'number'},
                    'maxconnections': {'type': 'integer'},
                    'ratio': {'type': 'number'},
                    'addpaused': {'type': 'boolean'},
                    'content_filename': {'type': 'string'},
                    'main_file_only': {'type': 'boolean', 'default': False},
                    'main_file_ratio': {'type': 'number', 'default': 0.9},
                    'magnetization_timeout': {'type': 'integer', 'default': 0},
                    'include_subs': {'type': 'boolean', 'default': False},
                    'bandwidthpriority': {'type': 'number'},
                    'honourlimits': {'type': 'boolean'},
                    'include_files': one_or_more({'type': 'string'}),
                    'skip_files': one_or_more({'type': 'string'}),
                    'rename_like_files': {'type': 'boolean', 'default': False},
                    'queue_position': {'type': 'integer'}
                },
                'additionalProperties': False
            }
        ]
    }

    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
            Call download plugin to generate the temp files we will load
            into transmission then verify they are valid torrents
        """
        config = prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        config = prepare_config(config)
        # don't add when learning
        if task.options.learn:
            return
        if not config['enabled']:
            return
        # Do not run if there is nothing to do
        if not task.accepted:
            return
        client = create_rpc_client(config)
        if task.accepted:
            add_to_transmission(client, task, config)

    def on_task_learn(self, task, config):
        """ Make sure all temp files are cleaned up when entries are learned """
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_learn


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmission, 'transmission', api_ver=2)
