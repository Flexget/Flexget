from __future__ import unicode_literals, division, absolute_import

import ftplib
import logging
import re

from ftputil.error import FTPOSError

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import DependencyError, PluginError

try:
    import ftputil
    import ftputil.session

    imported = True
except ImportError:
    imported = False

log = logging.getLogger('ftp_list')


class FTPList(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'host': {'type': 'string'},
            'port': {'type': 'integer'},
            'use_ssl': {'type': 'boolean'},
            'regexp': {'type': 'string', 'format': 'regex'},
            'directories': one_or_more({'type': 'string'}),
            'retrieve': one_or_more({'type': 'string', 'enum': ['files', 'dirs']}, unique_items=True)
        },
        'required': ['username', 'host']
    }

    @staticmethod
    def prepare_config(config):
        config.setdefault('retrieve', ['files'])
        config.setdefault('use_ssl', False)
        config.setdefault('dirs', ['.'])
        config.setdefault('port', 21)
        config.setdefault('regexp', '.')
        if not isinstance(config['dirs'], list):
            config['dirs'] = [config['dirs']]
        return config

    def _to_entry(self, object):
        entry = Entry()

        title = self.FTP.path.basename(object)
        location = self.FTP.path.abspath(object)

        entry['title'] = title
        entry['location'] = location
        entry['url'] = 'ftp://{}:{}@{}:{}/{}'.format(self.username, self.password, self.host, self.port, location)
        entry['filename'] = title

        log.debug('adding entry %s', entry)
        if entry.isvalid():
            return entry
        else:
            log.warning('tried to return an illegal entry: %s', entry)

    def on_task_input(self, task, config):
        if not imported:
            raise DependencyError('ftp_list', 'ftp_list', 'ftputil is required for this plugin')
        config = self.prepare_config(config)

        self.username = config.get('username')
        self.password = config.get('password')
        self.host = config.get('host')
        self.port = config.get('port')

        directories = config.get('dirs')
        match = re.compile(config['regexp'], re.IGNORECASE).match
        base_class = ftplib.FTP_TLS if config.get('use_ssl') else ftplib.FTP
        session_factory = ftputil.session.session_factory(port=self.port, base_class=base_class)
        try:
            log.verbose(
                'trying to establish connection to FTP: %s:<HIDDEN>@%s:%s', self.username, self.host, self.port)
            self.FTP = ftputil.FTPHost(self.host, self.username, self.password, session_factory=session_factory)
        except FTPOSError as e:
            raise PluginError('Could not connect to FTP: {}'.format(e.args[0]))

        entries = []
        with self.FTP as ftp:
            for base, dirs, files in ftp.walk(ftp.curdir):
                if not any(dir in base for dir in directories):
                    log.debug('dir %s is not in %s, skipping', base, directories)
                    continue
                if 'files' in config['retrieve']:
                    for file in files:
                        if match(file):
                            path = ftp.path.join(base, file)
                            entries.append(self._to_entry(path))
                if 'dirs' in config['retrieve']:
                    for dir in dirs:
                        if match(dir):
                            path = ftp.path.join(base, dir)
                            entries.append(self._to_entry(path))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(FTPList, 'ftp_list', api_ver=2)
