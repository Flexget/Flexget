# -*- coding: utf-8 -*-

from urllib import urlencode
from urllib2 import urlopen, URLError, HTTPError
from logging import getLogger
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError
from flexget import validator

log = getLogger('pyload')


class PluginPyLoad(object):
    """
      Add url from entry url to pyload

      Example:

      pyload:
        api: http://localhost:8000/api
        queue: yes
        username: myusername
        password: mypassword
        enabled: yes

    Default values for the config elements:

    pyload:
        api: http://localhost:8000/api
        queue: yes
        enabled: yes
    """

    __author__ = 'http://pyload.org'
    __version__ = '0.1'

    DEFAULT_API = 'http://localhost:8000/api'
    DEFAULT_QUEUE = True

    def __init__(self):
        self.session = None

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        root.accept('boolean')
        advanced = root.accept('dict')
        advanced.accept('text', key='api')
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('boolean', key='queue')
        return root

    def on_process_start(self, feed, config):
        self.session = None
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'queue': 'boolean'})

    def on_feed_output(self, feed, config):
        if not config.get('enabled', True):
            return
        if not feed.accepted:
            return
        self.add_entries(feed, config)

    def add_entries(self, feed, config):
        """Adds accepted entries"""

        try:
            self.check_login(feed, config)
        except URLError:
            raise PluginError('pyLoad not reachable', log)
        except Exception, e:
            raise PluginError('Unknown error: %s' % e)

        url = config.get('api', self.DEFAULT_API).rstrip('/')

        for entry in feed.accepted:
            if feed.manager.options.test:
                log.info('Would add `%s` to pyload' % entry['url'])
                continue

            try:
                dest = True if config.get('queue', self.DEFAULT_QUEUE) else False
                post = urlencode({'name': "'%s'" % entry['title'],
                                  'links': str([entry['url']]),
                                  'dest': dest,
                                  'session': self.session})
                result = urlopen(url + '/addPackage', post)
                log.debug('Package added: %s' % result)
            except Exception, e:
                feed.fail(entry, str(e))

    def check_login(self, feed, config):
        url = config.get('api', self.DEFAULT_API).rstrip('/')

        if not self.session:
            # Login
            post = urlencode({'username': config['username'], 'password': config['password']})
            result = urlopen(url + '/login', post)
            response = result.read()
            if response == 'false':
                raise PluginError('Login failed', log)
            self.session = response.replace('"', '')
        else:
            try:
                result = urlopen(url + '/getServerVersion')
            except HTTPError, e:
                if e.code == 401: # Not Authorized
                    self.session = None
                    return self.check_login(feed, config)
                else:
                    raise PluginError('HTTP Error %s' % e, log)


register_plugin(PluginPyLoad, 'pyload', api_ver=2)
