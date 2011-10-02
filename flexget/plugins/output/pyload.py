# -*- coding: utf-8 -*-

from urllib import urlencode
from urllib2 import urlopen, URLError, HTTPError
from logging import getLogger
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, DependencyError
from flexget import validator

log = getLogger('pyload')

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        raise DependencyError(issued_by='pyload', missing='simplejson',
                              message='pyload requires either simplejson module or python > 2.5')


class PluginPyLoad(object):
    """
      Add url from entry url to pyload

      Example:

      pyload:
        api: http://localhost:8000/api
        queue: yes
        username: myusername
        password: mypassword
        hoster:
          - YoutubeCom
        multihoster: yes
        enabled: yes

    Default values for the config elements:

    pyload:
        api: http://localhost:8000/api
        queue: no
        hoster: ALL
        multihoster: yes
        enabled: yes
    """

    __author__ = 'http://pyload.org'
    __version__ = '0.2'

    DEFAULT_API = 'http://localhost:8000/api'
    DEFAULT_QUEUE = False
    DEFAULT_HOSTER = []
    DEFAULT_MULTIHOSTER = True

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
        advanced.accept('list', key='hoster').accept('text')
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
        except Exception:
            raise PluginError('Unknown error', log)

        url = config.get('api', self.DEFAULT_API)
        hoster = config.get('hoster', self.DEFAULT_HOSTER)

        for entry in feed.accepted:
            # bunch of urls now going to check
            content = entry['description'] + " " + entry['url']

            result = query_api(url, "parseURLs", {"html": "'''%s'''" % content, "url": "''", "session": self.session})

            # parsed plugins : urls
            parsed = json.loads(result.read())

            urls = []

            # check for preferred hoster
            for name in hoster:
                if name in parsed:
                    urls.extend(parsed[name])
                    if not config.get('multihoster', self.DEFAULT_MULTIHOSTER):
                        break

            # no preferred hoster, add all recognized plugins
            if not urls:
                for name, purls in parsed.iteritems():
                    if name != "BasePlugin":
                        urls.extend(purls)


            if feed.manager.options.test:
                log.info('Would add `%s` to pyload' % urls)
                continue

            # no urls found
            if not urls:
                log.info("No suited urls in entry %s" % entry['name'])
                continue

            log.debug("Add %d urls to pyLoad" % len(urls))

            try:
                dest = True if config.get('queue', self.DEFAULT_QUEUE) else False
                post = {'name': "'%s'" % entry['title'],
                        'links': str(urls),
                        'dest': dest,
                        'session': self.session}

                result = query_api(url, "addPackage", post)
                log.debug('Package added: %s' % result)
            except Exception, e:
                feed.fail(entry, str(e))

    def check_login(self, feed, config):
        url = config.get('api', self.DEFAULT_API)

        if not self.session:
            # Login
            post = {'username': config['username'], 'password': config['password']}
            result = query_api(url, "login", post)
            response = result.read()
            if response == 'false':
                raise PluginError('Login failed', log)
            self.session = response.replace('"', '')
        else:
            try:
                query_api(url, 'getServerVersion')
            except HTTPError, e:
                if e.code == 403: # Forbidden
                    self.session = None
                    return self.check_login(feed, config)
                else:
                    raise PluginError('HTTP Error %s' % e, log)


def query_api(url, method, post=None):
    return urlopen(url.rstrip("/") + "/" + method.strip("/"), urlencode(post) if post else None)

register_plugin(PluginPyLoad, 'pyload', api_ver=2)
