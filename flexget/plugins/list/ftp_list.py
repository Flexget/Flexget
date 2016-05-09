from __future__ import unicode_literals, division, absolute_import

import ftplib
import logging
from collections import MutableSet

import ftputil.session
from ftputil.error import FTPOSError

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import DependencyError, PluginError

try:
    import ftputil

    imported = True
except ImportError:
    imported = False

log = logging.getLogger('ftp_list')


class FTPListSet(MutableSet):
    # Public interface

    def __init__(self, config):
        if not imported:
            raise DependencyError('ftp_list', 'ftp_list', 'ftputil is required for this plugin')
        self.config = config
        self._prepare_config()
        self.FTP = self._connect()

    def __iter__(self):
        return (entry for entry in self._list_entries())

    def __len__(self):
        return len(self._list_entries())

    def __contains__(self, entry):
        return self._entry_match(entry) is not None

    def discard(self, entry, ftp=None):
        match = self._entry_match(entry)
        if match:
            if not ftp:
                with self.FTP:
                    self.FTP.remove(match['location'])
            else:
                ftp.remove(match['location'])

    def add(self, entry, ftp=None):
        path = entry.get('location') or entry.get('path')
        if path:
            if not ftp:
                with self.FTP:
                    self.FTP.upload(path, '/')
            else:
                ftp.upload(path, '/')

    def __ior__(self, entries):
        with self.FTP as ftp:
            for entry in entries:
                self.add(entry, ftp)

    def __iand__(self, entries):
        with self.FTP as ftp:
            for entry in entries:
                self.discard(entry, ftp)

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        return set(it)

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    def get(self, entry):
        return self._entry_match(entry)

    # Internal methods

    def _prepare_config(self):
        self.config.setdefault('retrieve', ['files'])
        self.config.setdefault('use_ssl', False)

    def _connect(self):
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        self.host = self.config.get('host')
        self.port = self.config.get('port')
        self.dirs = self.config.get('dirs')
        base_class = ftplib.FTP_TLS if self.config.get('use_ssl') else ftplib.FTP
        session_factory = ftputil.session.session_factory(port=self.port, base_class=base_class)
        try:
            log.verbose(
                'trying to establish connection to FTP: {}:<HIDDEN>@{}:{}'.format(self.username, self.host, self.port))
            return ftputil.FTPHost(self.host, self.username, self.password, session_factory=session_factory)
        except FTPOSError as e:
            raise PluginError('Could not connect to FTP: {}'.format(e.args[0]))

    def _to_entry(self, base, object):
        entry = Entry()
        entry['title'] = object
        entry['location'] = '{}'.format(self.FTP.path.join(base, object))
        entry['url'] = 'ftp://{}:{}@{}:{}/{}'.format(self.username, self.password, self.host, self.port,
                                                     self.FTP.path.join(base, object))
        log.debug('adding entry {}'.format(entry))
        return entry

    def _list_entries(self):
        entries = []
        log.verbose('connected to FTP, starting to retrfile files and dirs')
        with self.FTP as ftp:
            for base, dirs, files in ftp.walk(ftp.curdir):
                if self.dirs and base not in self.dirs:
                    log.debug('dir {} is not in {}, skipping'.format(base, ' ,'.join(self.dirs)))
                    continue
                if 'files' in self.config['retrieve']:
                    for file in files:
                        entries.append(self._to_entry(base, file))
                if 'dirs' in self.config['retrieve']:
                    for dir in dirs:
                        entries.append(self._to_entry(base, dir))
        return entries

    def _entry_match(self, entry):
        for _entry in self._list_entries():
            if entry['title'] == _entry['title']:
                log.debug('entry match found: {}'.format(_entry))
                return _entry


class FTPList(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'host': {'type': 'string'},
            'port': {'type': 'integer'},
            'use_ssl': {'type': 'boolean'},
            'dirs': {'type': 'array', 'items': 'string'},
            'retrieve': one_or_more({'type': 'string', 'enum': ['files', 'dirs']}, unique_items=True)
        },
        'required': ['username', 'password', 'host', 'port']
    }

    @staticmethod
    def get_list(config):
        return FTPListSet(config)

    def on_task_input(self, task, config):
        return list(FTPListSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(FTPList, 'ftp_list', api_ver=2, groups=['list'])
