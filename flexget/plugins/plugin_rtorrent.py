from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

from pyrobase.io.xmlrpc2scgi import SCGIRequest
import xmlrpclib

log = logging.getLogger('rtorrent')


class RtorrentPlugin(object):

    # TODO: schema

    def prepare_config(self, config):
        config.setdefault('url', 'scgi://localhost:5000')
        config.setdefault('set', {})
        return config

    def request(self, config, method, *params):
        xmlreq = xmlrpclib.dumps(tuple(params), method)
        xmlresp = SCGIRequest(config['url']).send(xmlreq)
        return xmlrpclib.loads(xmlresp)[0][0]


    def on_task_start(self, task, config):
        config = self.prepare_config(config)

        # check connection to rtorrent
        # TODO: validate response
        resp = self.request(config, 'system.listMethods')

    def on_task_download(self, task, config):
        """
            Call download plugin to generate the temp files 
            we will load in client.

            This implementation was copied from Transmission plugin.
        """
        config = self.prepare_config(config)

        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    def on_task_output(self, task, config):
        """This method is based on Transmission plugin's implementation"""
        if task.options.learn:
            return
        if not task.accepted:
            return
        
        self.add_to_client(task, config)

    def add_to_client(self, task, config):
        for entry in task.accepted:
            if task.options.test:
                log.info('Would add %s to rtorrent' % entry['url'])
                continue
            if not self._check_downloaded(entry):
                continue

            # TODO ...


    def _check_downloaded(self, entry):
        """Check if file is downloaded and exists"""
        downloaded = not entry['url'].startswith('magnet:')
        # Check that file is downloaded
        if downloaded and 'file' not in entry:
            entry.fail('file missing?')
            return False
        # Verify the temp file exists
        if downloaded and not os.path.exists(entry['file']):
            tmp_path = os.path.join(task.manager.config_base, 'temp')
            log.debug('entry: %s' % entry)
            log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
            entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            return False
        return True

@event('plugin.register')
def register_plugin():
    plugin.register(RtorrentPlugin, 'rtorrent', api_ver=2)
