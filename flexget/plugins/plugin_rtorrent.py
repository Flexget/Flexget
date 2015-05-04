from __future__ import unicode_literals, division, absolute_import
import logging

import os
from time import sleep

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

try:
    from pyrobase.io.xmlrpc2scgi import SCGIRequest
except ImportError:
    SCGIRequest = None
import xmlrpclib


log = logging.getLogger('rtorrent')



class Rtorrent(object):
    """rTorrent API client"""

    default_fields = [
        'hash',
        'name',
        'up.total', 'down.total',
        'is_open', 'is_active',
        'custom1', 'custom2', 'custom3', 'custom4', 'custom5',
        'state', 'complete',
        'ratio',
        'directory', 'directory_base'
    ]

    def __init__(self, uri):
        if not SCGIRequest:
            raise plugin.PluginError('Dependency pyrobase not found')

        self.uri = uri
        self._version = None

    def request(self, method, params = []):
        # TODO: can we add a timeout?
        xml_req = xmlrpclib.dumps(tuple(params), method)
        xml_resp = SCGIRequest(self.uri).send(xml_req)
        return xmlrpclib.loads(xml_resp)[0][0]

    @property
    def version(self):
        if not self._version:
            resp = self.request('system.client_version')
            self._version = [int(v) for v in resp.split('.')]
        return self._version

    def load(self, data, options = {}, raw = False, start = False, mkdir = True):
        if raw:
            method = 'load.raw' + ('_start' if start else '')

            with open(data, 'rb') as f:
                data = xmlrpclib.Binary(f.read())
        else:
            method = 'load.' + ('start' if start else 'normal')

        # first param is empty string; not sure why, but it is required
        params = ['', data]

        # extra commands
        for key, val in options.iteritems():
            params.append('d.{0}.set={1}'.format(key, val))


        if mkdir and 'directory' in options:
            execute_method = 'execute.throw'
            execute_params = ['', 'mkdir', '-p', options['directory']]
            # TODO: execute this

        # The return value from load method is always 0, success or failure
        self.request(method, params)

    def verify_load(self, infohash, attempts = 3, delay = 0.5):
        """ Fetch and compare just the infohash. """
        for i in range(0, attempts):
            try:
                return self.request('d.hash', [infohash]) == infohash
            except:
                sleep(delay)
        raise

    def torrents(self, view = 'main', fields = None):
        if not fields:
            fields = self.default_fields
        params = ['d.{0}='.format(field) for field in fields]
        params.insert(0, view)

        resp = self.request('d.multicall', params)
        # Response is formatted as a list of lists, with just the values
        return [dict(zip(fields, val)) for val in resp]




class RtorrentPluginBase(object):

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        client = Rtorrent(config['uri'])
        if client.version < [0, 9, 4]:
            task.abort("rtorrent version >=0.9.4 required, found {0}"
                .format('.'.join(map(str, client.version))))


class RtorrentOutputPlugin(RtorrentPluginBase):

    schema = {
        'anyOf': [
            # allow construction with just a bool for enabled
            {'type': 'boolean'},
            # allow construction with just a URI
            {'type': 'string'},
            # allow construction with options
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    # connection info
                    'uri': {'type': 'string'},
                    # handling options
                    'start': {'type': 'boolean'},
                    # properties to set on rtorrent download object
                    'directory': {'type': 'string'},
                    'directory_base': {'type': 'string'},
                    'custom1': {'type': 'string'},
                    'custom2': {'type': 'string'},
                    'custom3': {'type': 'string'},
                    'custom4': {'type': 'string'},
                    'custom5': {'type': 'string'},
                },
                'additionalProperties': False
            }
        ]
    }


    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        if isinstance(config, str):
            config = {'uri': config}

        config.setdefault('enabled', True)
        config.setdefault('uri', 'scgi://localhost:5000')
        config.setdefault('start', True)

        return config

    def client_options(self, config):
        options = {}

        # These options can be copied as-is from config to options
        options_map_equal = [
            'directory', 'directory_base',
            'custom1', 'custom2', 'custom3', 'custom4', 'custom5'
        ]

        for option in options_map_equal:
            if option in config:
                options[option] = config[option]

        return options


    def on_task_download(self, task, config):
        """
        Call download plugin to generate the temp files 
        we will load in client.

        This implementation was copied from Transmission plugin.
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    def on_task_output(self, task, config):
        """This method is based on Transmission plugin's implementation"""
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        if task.options.learn:
            return
        if not task.accepted:
            return
        
        client = Rtorrent(config['uri'])
        options = self.client_options(config)

        for entry in task.accepted:
            if task.options.test:
                log.info('Would add {0} to rTorrent'.format(entry['url']))
                continue
            self.add_entry_to_client(client, entry, options, config['start'])

    def add_entry_to_client(self, client, entry, options, start):
        downloaded = not entry['url'].startswith('magnet:')

        # Check that file is downloaded
        if downloaded and 'file' not in entry:
            entry.fail('file missing?')
            return
        # Verify the temp file exists
        if downloaded and not os.path.exists(entry['file']):
            tmp_path = os.path.join(task.manager.config_base, 'temp')
            log.debug('entry: %s' % entry)
            log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
            entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            return

        
        data = entry['file'] if downloaded else entry['url']

        try:
            resp_load = client.load(data, options, downloaded, start)
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as e:
            entry.fail('Failed to add: {0}'.format(e))
            return
        log.debug('Add response: {0}'.format(resp_load))

        if 'torrent_info_hash' not in entry:
            log.info('Cannot verify add: we have no info-hash')
            return

        try:
            verified = client.verify_load(entry['torrent_info_hash'])
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as e:
            entry.fail('Failed to verify add: {0}'.format(e))
            return

        if not verified:
            entry.fail('Failed to verify add: info-hash not found')
            return

    def on_task_exit(self, task, config):
        """Make sure all temp files are cleaned up when task exists"""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_exit


class RtorrentInputPlugin(RtorrentPluginBase):

    schema = {
        'anyOf': [
            # allow construction with just a bool for enabled
            {'type': 'boolean'},
            # allow construction with just a URI
            {'type': 'string'},
            # allow construction with options
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    # connection info
                    'uri': {'type': 'string'},
                    # additional options
                    'view': {'type': 'string'},
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        if isinstance(config, str):
            config = {'uri': config}

        config.setdefault('enabled', True)
        config.setdefault('uri', 'scgi://localhost:5000')
        config.setdefault('view', 'main')

        return config


    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        client = Rtorrent(config['uri'])

        try:
            torrents = client.torrents(config['view'])
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as e:
            task.abort('Could not get torrents: {0}'.format(e))
            return

        entries = []
        for torrent in torrents:
            # TODO: add other fields like trackers, file, etc.
            entry = Entry(
                title=torrent['name'],
                torrent_info_hash=torrent['hash']
            )
            for attr in ['custom1', 'custom2', 'custom3', 'custom4', 'custom5']:
                entry['rtorrent_' + attr] = torrent[attr]

            entries.append(entry)

        return entries



@event('plugin.register')
def register_plugin():
    plugin.register(RtorrentOutputPlugin, 'rtorrent', api_ver=2)
    # plugin.register(RtorrentInputPlugin, 'from_rtorrent', api_ver=2)
    # plugin.register(RtorrentCleanupPlugin, 'clean_rtorrent', api_ver=2)
