"""Plugin for plex media server (www.plexapp.com)."""
from xml.dom.minidom import parse, parseString
import re
import logging
from flexget.utils import requests
from string import split
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry

log = logging.getLogger('plex')

class InputPlex(object):
    """
    Uses a plex media server (www.plexapp.com) tv section as an input.

    'section' is a required parameter, locate it at http://<yourplexserver>:32400/library/sections/
    'selection' can be set to different keys:
        - all
        - unwatched
        - recentlyAdded
        - recentlyViewed
        - recentlyViewedShows
      'all' and 'recentlyViewedShows' will only produce a list of show names while the other three will produce filename and download url 
    Default paramaters:
      server   : 'localhost'
      port     : 32400
      selection: all

    Example:

      plex:
        server: 192.168.1.23
        section: 3
    """
    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='server')
        config.accept('text', key='selection')
        config.accept('integer', key='port')
        config.accept('integer', key='section', required=True)
        config.accept('text', key='username')
        config.accept('text', key='password')
        return config

    def prepare_config(self, config):
        config.setdefault('server', 'localhost')
        config.setdefault('port', 32400)
        config.setdefault('selection', 'all');
        config.setdefault('username', '')
        config.setdefault('password', '')
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        accesstoken = ""
        if config['username'] and config['password'] and config['server'] != 'localhost':
            header = {'X-Plex-Client-Identifier': 'flexget'} 
            log.debug("Trying to to connect to myplex.")
            try:
                r = requests.post('https://my.plexapp.com/users/sign_in.xml', auth=(config['username'], config['password']), headers=header)
            except requests.RequestException as e:
                raise PluginError('Could not login to my.plexapp.com: %s. Username: %s Password: %s' % (e, config['username'], config['password']))
            log.debug("Managed to connect to myplex.")
            if 'Invalid email' in r.text:
                raise PluginError('Could not login to my.plexapp.com: invalid username and/or password!')
            log.debug("Managed to login to myplex.")
            dom = parseString(r.text)
            plextoken = dom.getElementsByTagName('authentication-token')[0].firstChild.nodeValue
            log.debug("Got plextoken: %s" % plextoken)
            try:
                r = requests.get("https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % plextoken)
            except requests.RequestException as e:
                raise PluginError('Could not get servers from my.plexapp.com using authentication-token: %s.' % plextoken)
            dom = parseString(r.text)
            for node in  dom.getElementsByTagName('Server'):
                if node.getAttribute('address') == config['server']:
                    accesstoken = node.getAttribute('accessToken') 
                    log.debug("Got accesstoken: %s" % plextoken)
                    accesstoken = "?X-Plex-Token=%s" % accesstoken
            if accesstoken == "":
                raise PluginError('Could not retrieve accesstoken for %s.' % config['server'])
        try:
            r = requests.get("http://%s:%d/library/sections/%d/%s%s" % (config['server'], config['port'], config['section'], config['selection'], accesstoken))
        except requests.RequestException as e:
            raise PluginError('Error retrieving source: %s' % e)
        dom = parseString(r.text.encode("utf-8"))
        entries = []
        if config['selection'] == 'all' or config['selection'] == 'recentlyViewedShows':
            for node in dom.getElementsByTagName('Directory'):
                title=node.getAttribute('title')
                title=re.sub(r'^(.*)\(\d+\)$', r'\1', title)
                title=re.sub(r'[\(\)]', r'', title)
                title=re.sub(r'\&', r'And', title)
                title=re.sub(r'[^A-Za-z0-9- ]', r'', title)
                e = Entry()
                e['title'] = title
                e['url'] = "NULL"
                entries.append(e)
        else:
            for node in dom.getElementsByTagName('Video'):
                for media in node.getElementsByTagName('Media'):
                    for part in media.getElementsByTagName('Part'):
                        key = part.getAttribute('key')
                        tmp = part.getAttribute('file')
                        title = split(tmp, "/")[-1]
                e = Entry()
                e['title'] = title
                e['url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, accesstoken)
                entries.append(e)
        return entries

register_plugin(InputPlex, 'plex', api_ver=2)
