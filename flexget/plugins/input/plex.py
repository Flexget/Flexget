"""Plugin for plex media server (www.plexapp.com)."""
from xml.dom.minidom import parse
import urllib2
import re
import logging
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
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        u = urllib2.Request("http://%s:%d/library/sections/%d/%s" % (config['server'], config['port'], config['section'], config['selection']))
        if config['username'] and config['password']:
            u.add_header = [('X-Plex-User', '%s' % config['username']), ('X-Plex-Pass', '%s' % config['password'])] 
        try:
            datasource = urllib2.urlopen(u)
        except urllib2.URLError, (err):
            raise PluginError('Error retrieving source: %s' % err)
        dom = parse(datasource)
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
                e['url'] = "http://%s:%d%s" % (config['server'], config['port'], key)
                entries.append(e)
        return entries

register_plugin(InputPlex, 'plex', api_ver=2)
