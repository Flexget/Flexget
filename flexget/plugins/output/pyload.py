# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from logging import getLogger
from urllib import quote

from requests.exceptions import RequestException

from flexget import plugin, validator
from flexget.event import event
from flexget.utils import json, requests

log = getLogger('pyload')


class PluginPyLoad(object):
    """
    Parse task content or url for hoster links and adds them to pyLoad.

    Example::

      pyload:
        api: http://localhost:8000/api
        queue: yes
        username: my_username
        password: my_password
        folder: desired_folder
        package: desired_package_name (jinja2 supported)
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
    __version__ = '0.4'

    DEFAULT_API = 'http://localhost:8000/api'
    DEFAULT_QUEUE = False
    DEFAULT_FOLDER = ''
    DEFAULT_HOSTER = []
    DEFAULT_PARSE_URL = False
    DEFAULT_MULTIPLE_HOSTER = True
    DEFAULT_PREFERRED_HOSTER_ONLY = False
    DEFAULT_HANDLE_NO_URL_AS_FAILURE = False

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        root.accept('boolean')
        advanced = root.accept('dict')
        advanced.accept('text', key='api')
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('text', key='folder')
        advanced.accept('text', key='package')
        advanced.accept('boolean', key='queue')
        advanced.accept('boolean', key='parse_url')
        advanced.accept('boolean', key='multiple_hoster')
        advanced.accept('list', key='hoster').accept('text')
        advanced.accept('boolean', key='preferred_hoster_only')
        advanced.accept('boolean', key='handle_no_url_as_failure')
        return root

    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return

        self.add_entries(task, config)

    def add_entries(self, task, config):
        """Adds accepted entries"""

        try:
            session = self.get_session(config)
        except IOError:
            raise plugin.PluginError('pyLoad not reachable', log)
        except plugin.PluginError:
            raise
        except Exception as e:
            raise plugin.PluginError('Unknown error: %s' % str(e), log)

        api = config.get('api', self.DEFAULT_API)
        hoster = config.get('hoster', self.DEFAULT_HOSTER)
        folder = config.get('folder', self.DEFAULT_FOLDER)

        for entry in task.accepted:
            # bunch of urls now going to check
            content = entry.get('description', '') + ' ' + quote(entry['url'])
            content = json.dumps(content.encode("utf8"))

            url = json.dumps(entry['url']) if config.get('parse_url', self.DEFAULT_PARSE_URL) else "''"

            log.debug("Parsing url %s" % url)

            result = query_api(api, "parseURLs", {"html": content, "url": url, "session": session})

            # parsed { plugins: [urls] }
            parsed = result.json()

            urls = []

            # check for preferred hoster
            for name in hoster:
                if name in parsed:
                    urls.extend(parsed[name])
                    if not config.get('multiple_hoster', self.DEFAULT_MULTIPLE_HOSTER):
                        break

            # no preferred hoster and not preferred hoster only - add all recognized plugins
            if not urls and not config.get('preferred_hoster_only', self.DEFAULT_PREFERRED_HOSTER_ONLY):
                for name, purls in parsed.iteritems():
                    if name != "BasePlugin":
                        urls.extend(purls)

            if task.options.test:
                log.info('Would add `%s` to pyload' % urls)
                continue

            # no urls found
            if not urls:
                if config.get('handle_no_url_as_failure', self.DEFAULT_HANDLE_NO_URL_AS_FAILURE):
                    entry.fail("No suited urls in entry %s" % entry['title'])
                else:
                    log.info("No suited urls in entry %s" % entry['title'])
                continue

            log.debug("Add %d urls to pyLoad" % len(urls))

            try:
                dest = 1 if config.get('queue', self.DEFAULT_QUEUE) else 0  # Destination.Queue = 1

                # Use the title of the enty, if no naming schema for the package is defined.
                name = config.get('package', entry['title'])

                # If name has jinja template, render it
                try:
                    name = entry.render(name)
                except RenderError as e:
                    name = entry['title']
                    log.error('Error rendering jinja event: %s' % e)

                post = {'name': "'%s'" % name.encode("ascii", "ignore"),
                        'links': str(urls),
                        'dest': dest,
                        'session': session}

                pid = query_api(api, "addPackage", post).text
                log.debug('added package pid: %s' % pid)

                if folder:
                    # set folder with api
                    data = {'folder': folder}
                    query_api(api, "setPackageData", {'pid': pid, 'data': data, 'session': session})

            except Exception as e:
                entry.fail(str(e))

    def get_session(self, config):
        url = config.get('api', self.DEFAULT_API)

        # Login
        post = {'username': config['username'], 'password': config['password']}
        result = query_api(url, "login", post)
        response = result.json()
        if not response:
            raise plugin.PluginError('Login failed', log)
        return response.replace('"', '')


def query_api(url, method, post=None):
    try:
        response = requests.request(
            'post' if post is not None else 'get',
            url.rstrip("/") + "/" + method.strip("/"),
            data=post)
        response.raise_for_status()
        return response
    except RequestException as e:
        if e.response.status_code == 500:
            raise plugin.PluginError('Internal API Error: <%s> <%s> <%s>' % (method, url, post), log)
        raise


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPyLoad, 'pyload', api_ver=2)
