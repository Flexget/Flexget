from __future__ import unicode_literals, division, absolute_import
import logging

import os

from flexget import plugin
from flexget.event import event

try:
    from pyrobase.io.xmlrpc2scgi import SCGIRequest
except ImportError:
    SCGIRequest = None
import xmlrpclib


log = logging.getLogger('rtorrent')



class RtorrentPlugin(object):

    schema = {
        'anyOf': [
            # allow construction with just a bool for enabled
            {'type': 'boolean'},
            # allow construction with options
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    # connection info
                    'url': {'type': 'string'},
                    # properties to set on rtorrent download object
                    'set': {
                        'type': 'object',
                        'properties': {
                            'directory': {'type': 'string'},
                            'custom1': {'type': 'string'}
                        }
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('url', 'scgi://localhost:5000')
        config.setdefault('set', {})
        return config

    
    def request(self, config, method, params = []):
        # TODO: can we add timeout or something?
        xmlreq = xmlrpclib.dumps(tuple(params), method)
        xmlresp = SCGIRequest(config['url']).send(xmlreq)
        return xmlrpclib.loads(xmlresp)[0][0]


    def on_task_start(self, task, config):
        # Check dependencies
        if SCGIRequest is None:
            raise plugin.PluginError('pyrobase is required to use this plugin')

        config = self.prepare_config(config)
        if not config['enabled']:
            return

        # TODO: check connection to rtorrent, validate response
        # resp = self.request(config, 'system.listMethods')
        # if fail, raise PluginError

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
        if task.options.learn:
            return
        if not task.accepted:
            return
        if not config['enabled']:
            return
        
        self.add_to_client(task, config)

    def add_to_client(self, task, config):
        for entry in task.accepted:
            if task.options.test:
                log.info('Would add %s to rtorrent' % entry['url'])
                continue

            """Check if file is downloaded and exists"""
            downloaded = not entry['url'].startswith('magnet:')
            # Check that file is downloaded
            if downloaded and 'file' not in entry:
                entry.fail('file missing?')
                continue
            # Verify the temp file exists
            if downloaded and not os.path.exists(entry['file']):
                tmp_path = os.path.join(task.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            # not sure if empty string param is only for downloaded or not
            params = ['']

            # first param is data/url
            if downloaded:
                with open(entry['file'], 'rb') as f:
                    params.append(xmlrpclib.Binary(f.read()))
            else:
                params.append(entry['url'])

            # add additional params
            for key, val in config['set'].iteritems():
                params.append("d.{0}.set={1}".format(key, val))

            # TODO: add config option to specify if autostart
            # options: {, raw} {verbose, start}
            load_method = 'load.' + ('raw_' if downloaded else '') + 'verbose'

            try:
                resp = self.request(config, load_method, params)
            except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as e:
                entry.fail('Failed to add with exception: {0}'.format(e))
                continue

            log.debug('rtorrent add response: {0}'.format(resp))

            # verify torrent is added
            if 'torrent_info_hash' in entry:
                try:
                    respHash = self.request(config, 'd.hash', [entry['torrent_info_hash']])
                except (xmlrpclib.Fault, xmlrpclib.ProtocolError) as e:
                    entry.fail('Failed to verify add with exception: {0}'.format(e))
                    continue

                log.debug('rtorrent verify response: {0}'.format(respHash))
                if respHash != entry['torrent_info_hash']:
                    entry.fail('Failed to verify add: info hash not found')
                    continue
            else:
                log.debug('Cannot verify add because we have no info hash')



@event('plugin.register')
def register_plugin():
    plugin.register(RtorrentPlugin, 'rtorrent', api_ver=2)
