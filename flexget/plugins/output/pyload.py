from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

from logging import getLogger

from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.config_schema import one_or_more
from flexget.utils.template import RenderError

log = getLogger('pyload')


class PyloadApi(object):
    def __init__(self, requests, url):
        self.requests = requests
        self.url = url

    def get_session(self, config):
        # Login
        post = {'username': config['username'], 'password': config['password']}
        result = self.query("login", post)
        response = result.json()
        if not response:
            raise plugin.PluginError('Login failed', log)
        return response.replace('"', '')

    def query(self, method, post=None):
        try:
            response = self.requests.request(
                'post' if post is not None else 'get',
                self.url.rstrip("/") + "/" + method.strip("/"),
                data=post)
            response.raise_for_status()
            return response
        except RequestException as e:
            if e.response and e.response.status_code == 500:
                raise plugin.PluginError('Internal API Error: <%s> <%s> <%s>' % (method, self.url, post), log)
            raise


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
        package_password: desired_package_password
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
    __version__ = '0.5'

    DEFAULT_API = 'http://localhost:8000/api'
    DEFAULT_QUEUE = False
    DEFAULT_FOLDER = ''
    DEFAULT_HOSTER = []
    DEFAULT_PARSE_URL = False
    DEFAULT_MULTIPLE_HOSTER = True
    DEFAULT_PREFERRED_HOSTER_ONLY = False
    DEFAULT_HANDLE_NO_URL_AS_FAILURE = False

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'object',
                'properties': {
                    'api': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'folder': {'type': 'string'},
                    'package': {'type': 'string'},
                    'package_password': {'type': 'string'},
                    'queue': {'type': 'boolean'},
                    'parse_url': {'type': 'boolean'},
                    'multiple_hoster': {'type': 'boolean'},
                    'hoster': one_or_more({'type': 'string'}),
                    'preferred_hoster_only': {'type': 'boolean'},
                    'handle_no_url_as_failure': {'type': 'boolean'},
                    'enabled': {'type': 'boolean'},

                },
                'additionalProperties': False
             }
        ]
    }

    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return

        self.add_entries(task, config)

    def add_entries(self, task, config):
        """Adds accepted entries"""

        apiurl = config.get('api', self.DEFAULT_API)
        api = PyloadApi(task.requests, apiurl)

        try:
            session = api.get_session(config)
        except IOError:
            raise plugin.PluginError('pyLoad not reachable', log)
        except plugin.PluginError:
            raise
        except Exception as e:
            raise plugin.PluginError('Unknown error: %s' % str(e), log)

        hoster = config.get('hoster', self.DEFAULT_HOSTER)

        for entry in task.accepted:
            # bunch of urls now going to check
            content = entry.get('description', '') + ' ' + quote(entry['url'])
            content = json.dumps(content)

            url = json.dumps(entry['url']) if config.get('parse_url', self.DEFAULT_PARSE_URL) else "''"

            log.debug("Parsing url %s" % url)

            result = api.query("parseURLs", {"html": content, "url": url, "session": session})

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
                for name, purls in parsed.items():
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

                # Use the title of the entry, if no naming schema for the package is defined.
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

                pid = api.query("addPackage", post).text
                log.debug('added package pid: %s' % pid)

                # Set Folder
                folder = config.get('folder', self.DEFAULT_FOLDER)
                folder = entry.get('path', folder)
                if folder:
                    # If folder has jinja template, render it
                    try:
                        folder = entry.render(folder)
                    except RenderError as e:
                        folder = self.DEFAULT_FOLDER
                        log.error('Error rendering jinja event: %s' % e)
                    # set folder with api
                    data = json.dumps({'folder': folder})
                    api.query("setPackageData", {'pid': pid, 'data': data, 'session': session})
                
                # Set Package Password
                package_password = config.get('package_password')
                if package_password:
                    data = json.dumps({'password': package_password})
                    api.query("setPackageData", {'pid': pid, 'data': data, 'session': session})

            except Exception as e:
                entry.fail(str(e))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPyLoad, 'pyload', api_ver=2)
