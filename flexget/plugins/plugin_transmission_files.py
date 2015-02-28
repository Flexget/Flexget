from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget import plugin, validator
from flexget.entry import Entry
from flexget.event import event

from flexget.config_schema import one_or_more
from flexget.plugins.plugin_transmission import TransmissionBase


class PluginTransmissionFiles(TransmissionBase):

    """
    Returns the files currently available in the torrents on a transmission instance.

    You can filter by torrent info hassh and by returning only completed files:

    Example::

      transmission_files:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        
    Default values for the config elements::

      transmission_files:
        host: localhost
        port: 9091
        enabled: yes
        onlycomplete: yes    
    """

    schema = {
        'anyOf': [
            {'type': 'object'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'netrc': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'info_hash': {"oneOf": [{'type': 'string'}, {'type': 'array'}]},
                    'enabled': {'type': 'boolean'},
                    'onlycomplete': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
        config.setdefault('info_hash', None)
        config.setdefault('onlycomplete', True)
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        if not self.client:
            self.client = self.create_rpc_client(config)
        entries = []

        # Hack/Workaround for http://flexget.com/ticket/2002
        # TODO: Proper fix
        if 'username' in config and 'password' in config:
            self.client.http_handler.set_authentication(self.client.url, config['username'], config['password'])

        session = self.client.get_session()
        torrents = self.client.get_torrents(config['info_hash'])

        for torrent in torrents:
            dl_dir = torrent.downloadDir
            torrent_files = torrent.files().values()

            for file in torrent_files:
                if file['completed'] >= file['size'] or not config['onlycomplete']:
                    # TODO: Allow override to Windows-style paths
                    relpath = file['name']
                    fullpath = os.path.join(dl_dir, relpath)
                    filename = os.path.basename(relpath)
                    url = 'file://%s' % fullpath[1:]

                    entry = Entry(title=torrent.name, 
                                  location=relpath,
                                  location_full=fullpath, 
                                  filename=filename, 
                                  url=url, 
                                  torrent_info_hash=torrent.hashString,
                                  size=file['size'])

                    entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmissionFiles, 'transmission_files', api_ver=2)
