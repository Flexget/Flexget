# -*- coding: utf-8 -*-

from urllib import urlencode, quote
from urllib2 import urlopen, URLError, HTTPError
from logging import getLogger
from flexget.utils import json
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, DependencyError
from flexget import validator

log = getLogger('pyload')


class PluginPyLoad(object):
    """
    Parse feed content or url for hoster links and adds them to pyLoad.

    Example::

      pyload:
        api: http://localhost:8000/api
        queue: yes
        username: my_username
        password: my_password
        folder: desired_folder
        hoster:
          - YoutubeCom
        parse_url: no
        multiple_hoster: yes
        enabled: yes

    Default values for the config elements::

      pyload:
          api: http://localhost:8000/api
          queue: no
          hoster: ALL
          parse_url: no
          multiple_hoster: yes
          enabled: yes
    """

    __author__ = 'http://pyload.org'
    __version__ = '0.3'

    DEFAULT_API = 'http://localhost:8000/api'
    DEFAULT_QUEUE = False
    DEFAULT_FOLDER = ''
    DEFAULT_HOSTER = []
    DEFAULT_PARSE_URL = False
    DEFAULT_MULTIPLE_HOSTER = True

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
        advanced.accept('text', key='folder')
        advanced.accept('boolean', key='queue')
        advanced.accept('boolean', key='parse_url')
        advanced.accept('boolean', key='multiple_hoster')
        advanced.accept('list', key='hoster').accept('text')
        return root

    def on_process_start(self, feed, config):
        self.session = None

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
        except PluginError:
            raise
        except Exception, e:
            raise PluginError('Unknown error: %s' % str(e), log)

        api = config.get('api', self.DEFAULT_API)
        hoster = config.get('hoster', self.DEFAULT_HOSTER)
        folder = config.get('folder', self.DEFAULT_FOLDER)

        for entry in feed.accepted:
            # bunch of urls now going to check
            content = entry['description'] + " " + quote(entry['url'])
            content = json.dumps(content.encode("utf8"))

            url = json.dumps(entry['url']) if config.get('parse_url', self.DEFAULT_PARSE_URL) else "''"

            log.debug("Parsing url %s" % url)

            result = query_api(api, "parseURLs", {"html": content, "url": url, "session": self.session})

            # parsed { plugins: [urls] }
            parsed = json.loads(result.read())

            urls = []

            # check for preferred hoster
            for name in hoster:
                if name in parsed:
                    urls.extend(parsed[name])
                    if not config.get('multihoster', self.DEFAULT_MULTIPLE_HOSTER):
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
                log.info("No suited urls in entry %s" % entry['title'])
                continue

            log.debug("Add %d urls to pyLoad" % len(urls))

            try:
                dest = 1 if config.get('queue', self.DEFAULT_QUEUE) else 0  # Destination.Queue = 1
                post = {'name': "'%s'" % entry['title'],
                        'links': str(urls),
                        'dest': dest,
                        'session': self.session}

                pid = query_api(api, "addPackage", post).read()
                log.debug('added package pid: %s' % pid)

                if folder:
                    # set folder with api
                    data = {'folder': folder}
                    query_api(api, "setPackageData", {'pid': pid, 'data': data, 'session': self.session})

            except Exception, e:
                feed.fail(entry, str(e))

    def check_login(self, feed, config):
        url = config.get('api', self.DEFAULT_API)

        if not self.session:
            # Login
            post = {'username': config['username'], 'password': config['password']}
            result = query_api(url, "login", post)
            response = json.loads(result.read())
            if not response:
                raise PluginError('Login failed', log)
            self.session = response.replace('"', '')
        else:
            try:
                query_api(url, 'getServerVersion', {'session': self.session})
            except HTTPError, e:
                if e.code == 403:  # Forbidden
                    self.session = None
                    return self.check_login(feed, config)
                else:
                    raise PluginError('HTTP Error %s' % e, log)


def query_api(url, method, post=None):
    try:
        return urlopen(url.rstrip("/") + "/" + method.strip("/"), urlencode(post) if post else None)
    except HTTPError, e:
        if e.code == 500:
            raise PluginError('Internal API Error', log)
        raise

register_plugin(PluginPyLoad, 'pyload', api_ver=2)
