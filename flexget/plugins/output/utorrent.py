# -*- coding: utf-8 -*-


from __future__ import unicode_literals, division, absolute_import
import os
from logging import getLogger

from flexget import plugin
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.template import RenderError

log = getLogger('utorrent')


class PluginUtorrent(object):
    """
    Parse task content or url for hoster links and adds them to utorrent.

    Example::

      utorrent:
        url: http://localhost:8080/gui/
        username: my_username
        password: my_password
        path: Series

    """

    __author__ = 'Nil'
    __version__ = '0.1'

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'path': {'type': 'string'}
        },
        'required': ['username', 'password', 'url'],
        'additionalProperties': False
    }
    
    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
            Call download plugin to generate the temp files we will load
            into deluge then verify they are valid torrents
        """
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            for entry in task.accepted:
                download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    @plugin.priority(135)
    # @plugin.internet(log)
    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return
        # don't add when learning
        if task.options.learn:
            return

        session = requests.Session()
        url = config['url']
        if not url.endswith('/'):
            url += '/'
        auth = (config['username'], config['password'])
        # Login
        try:
            response = session.get(url + 'token.html', auth=auth)
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response.status_code == '401':
                raise plugin.PluginError('Invalid credentials, check your utorrent webui username and password.', log)
            raise plugin.PluginError('%s' % e, log)
        token = get_soup(response.text).find('div', id='token').text
        result = session.get(url, auth=auth, params={'action': 'list-dirs', 'token': token}).json()
        download_dirs = dict((os.path.normcase(dir['path']), i) for i, dir in enumerate(result['download-dirs']))
        
        for entry in task.accepted:
            # bunch of urls now going to check
            
            folder = 0
            path = entry.get('path', config.get('path', ''))
            try:
                path = os.path.expanduser(entry.render(path))
            except RenderError as e:
                log.error('Could not render path for `%s` downloading to default directory.' % entry['title'])
                # Add to default folder
                path = ''
            if path:
                path_normcase = os.path.normcase(path)
                
                for dir in download_dirs:
                    if path_normcase.startswith(dir):
                        folder = download_dirs[dir]
                        path = path[len(dir):].lstrip('\\')
                        break
                else:
                    log.error('path `%s` (or one of its parents)is not added to utorrent webui allowed download '
                              'directories. You must add it there before you can use it from flexget. '
                              'Adding to default download directory instead.' % path)
                    path = ''

            if task.options.test:
                log.info('Would add `%s` to utorrent' % entry['title'])
                continue

            # Get downloaded
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
            
            # Add torrent
            if downloaded:
                # HTTP://[IP]:[PORT]/GUI/?ACTION=ADD-FILE
                files = {'torrent_file': open(entry['file'], 'rb')}
                data = {'action': 'add-file', 'token': token, 'download_dir': folder, 'path': path}
                result = session.post(url, params=data, auth=auth, files=files)
            else:
                # http://[IP]:[PORT]/gui/?action=add-url&s=[TORRENT URL]
                data = {'action': 'add-url', 's': entry['url'], 'token': token, 'download_dir': folder, 'path': path}
                result = session.get(url, params=data, auth=auth)
                
            # Check result
            if 'build' in result.json():
                log.info('Added `%s` to utorrent' % entry['url'])
                log.info('in folder %s ' % folder + path)
            else:
                entry.fail('Fail to add `%s` to utorrent' % entry['url'])

    def on_task_exit(self, task, config):
        """Make sure all temp files are cleaned up when task exits"""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)
            
    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginUtorrent, 'utorrent', api_ver=2)
