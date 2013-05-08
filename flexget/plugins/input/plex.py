"""Plugin for plex media server (www.plexapp.com)."""
from xml.dom.minidom import parse
import urllib2
import re
import logging
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry

log = logging.getLogger('plex')

class InputPlex(object):
    """
    Uses a plex media server (www.plexapp.com) tv section as an input.

    'section' is a required parameter, locate it at http://<yourplexserver>:32400/library/sections/
    Default paramaters:
      server: 'localhost'
      port  : 32400

    Example:

      plex:
        server: 192.168.1.23
        section: 3
    """
    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='server')
        config.accept('integer', key='port')
        config.accept('integer', key='section', required=True)
        return config

    def prepare_config(self, config):
        config.setdefault('server', 'localhost')
        config.setdefault('port', 32400)
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        url = "http://" + config['server'] + ":" + str(config['port']) + "/library/sections/" + str(config['section']) + "/all"
        try:
            datasource = urllib2.urlopen(url)
        except urllib2.URLError, (err):
            raise PluginError('Error retrieving source: %s' % err)
        dom = parse(datasource)
        entries = []
        for node in dom.getElementsByTagName('Directory'):
            title=node.getAttribute('title')
            title=re.sub(r'^(.*)\(\d+\)$', r'\1', title)
            title=re.sub(r'[\(\)]', r'', title)
            title=re.sub(r'\&', r'And', title)
            title=re.sub(r'[^A-Za-z0-9- ]', r'', title)
            e = Entry()
            e['title'] = title
            e['url'] = "noop"
            entries.append(e)
        return entries

register_plugin(InputPlex, 'plex', api_ver=2)
