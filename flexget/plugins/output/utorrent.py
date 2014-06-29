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

    @plugin.internet(log)
    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
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
            # http://[IP]:[PORT]/gui/?action=add-url&s=[TORRENT URL]
            # bunch of urls now going to check
            folder = 0
            path = entry.get('path', config.get('path', ''))
            try:
                path = os.path.normcase(os.path.expanduser(entry.render(path)))
            except RenderError as e:
                log.error('Could not render path for `%s` downloading to default directory.' % entry['title'])
                # Add to default folder
                path = ''
            if path:
                for dir in download_dirs:
                    if path.startswith(dir):
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

            # Add torrent
            data = {'action': 'add-url', 's': entry['url'], 'token': token, 'download_dir': folder, 'path': path}
            result = session.get(url, params=data, auth=auth)
            if 'build' in result.json():
                log.info('Added `%s` to utorrent' % entry['url'])
                log.info('in folder %s ' % folder + path)
            else:
                entry.fail('Fail to add `%s` to utorrent' % entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(PluginUtorrent, 'utorrent', api_ver=2)
