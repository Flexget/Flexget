from urllib.parse import quote

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError

logger = logger.bind(name='pyload')


class PyloadApi:
    def __init__(self, requests, url):
        self.requests = requests
        self.url = url

    def get_session(self, config):
        # Login
        data = {'username': config['username'], 'password': config['password']}
        result = self.post('login', data=data)
        response = result.json()
        if not response:
            raise plugin.PluginError('Login failed', logger)

        if isinstance(response, str):
            return response.replace('"', '')
        return response

    def get(self, method):
        try:
            return self.requests.get(self.url.rstrip('/') + '/' + method.strip('/'))
        except RequestException as e:
            if e.response and e.response.status_code == 500:
                raise plugin.PluginError(f'Internal API Error: <{method}> <{self.url}>', logger)
            raise

    def post(self, method, data):
        try:
            return self.requests.post(self.url.rstrip('/') + '/' + method.strip('/'), data=data)
        except RequestException as e:
            if e.response and e.response.status_code == 500:
                raise plugin.PluginError(
                    f'Internal API Error: <{method}> <{self.url}> <{data}>', logger
                )
            raise


class PluginPyLoad:
    """Parse task content or url for hoster links and adds them to pyLoad.

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
        'type': 'object',
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
        'required': ['username', 'password'],
        'additionalProperties': False,
    }

    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return

        self.add_entries(task, config)

    def add_entries(self, task, config):
        """Add accepted entries."""
        apiurl = config.get('api', self.DEFAULT_API)
        api = PyloadApi(task.requests, apiurl)

        try:
            session = api.get_session(config)
        except OSError:
            raise plugin.PluginError('pyLoad not reachable', logger)
        except plugin.PluginError:
            raise
        except Exception as e:
            raise plugin.PluginError(f'Unknown error: {e!s}', logger)

        # old pyload (stable)
        is_pyload_ng = False
        parse_urls_command = 'parseURLs'
        add_package_command = 'addPackage'
        set_package_data_command = 'setPackageData'
        package_id_parameter = 'pid'
        folder_key = 'folder'

        # pyload-ng is returning dict instead of session string on login
        if isinstance(session, dict):
            is_pyload_ng = True
            parse_urls_command = 'parse_urls'
            add_package_command = 'add_package'
            set_package_data_command = 'set_package_data'
            package_id_parameter = 'package_id'
            folder_key = '_folder'

        hoster = config.get('hoster', self.DEFAULT_HOSTER)

        for entry in task.accepted:
            # bunch of urls now going to check
            contents = []
            description = entry.get('description')
            if description is not None:
                contents.append(description)
            contents.append(quote(entry['url']))
            content = ' '.join(contents)

            content = repr(content)

            if is_pyload_ng:
                url = repr(entry['url'] if config.get('parse_url', self.DEFAULT_PARSE_URL) else '')
            else:
                url = (
                    json.dumps(entry['url'])
                    if config.get('parse_url', self.DEFAULT_PARSE_URL)
                    else "''"
                )

            logger.debug('Parsing url {}', url)

            data = {'html': content, 'url': url}
            if not is_pyload_ng:
                data['session'] = session
            result = api.post(parse_urls_command, data=data)

            parsed = result.json()

            urls = entry.get('urls', [])

            # check for preferred hoster
            for name in hoster:
                if name in parsed:
                    urls.extend(parsed[name])
                    if not config.get('multiple_hoster', self.DEFAULT_MULTIPLE_HOSTER):
                        break

            # no preferred hoster and not preferred hoster only - add all recognized plugins
            if not urls and not config.get(
                'preferred_hoster_only', self.DEFAULT_PREFERRED_HOSTER_ONLY
            ):
                for name, purls in parsed.items():
                    if name != 'BasePlugin':
                        urls.extend(purls)

            if task.options.test:
                logger.info('Would add `{}` to pyload', urls)
                continue

            # no urls found
            if not urls:
                if config.get('handle_no_url_as_failure', self.DEFAULT_HANDLE_NO_URL_AS_FAILURE):
                    entry.fail('No suited urls in entry {}'.format(entry['title']))
                else:
                    logger.info('No suited urls in entry {}', entry['title'])
                continue

            logger.debug('Add {} urls to pyLoad', len(urls))

            try:
                dest = 1 if config.get('queue', self.DEFAULT_QUEUE) else 0  # Destination.Queue = 1

                # Use the title of the entry, if no naming schema for the package is defined.
                name = config.get('package', entry['title'])

                # If name has jinja template, render it
                try:
                    name = entry.render(name)
                except RenderError as e:
                    name = entry['title']
                    logger.error('Error rendering jinja event: {}', e)

                if is_pyload_ng:
                    data = {
                        'name': repr(name.encode('ascii', 'ignore').decode()),
                        'links': repr(urls),
                        'dest': dest,
                    }
                else:
                    data = {
                        'name': json.dumps(name.encode('ascii', 'ignore').decode()),
                        'links': json.dumps(urls),
                        'dest': json.dumps(dest),
                        'session': session,
                    }

                pid = api.post(add_package_command, data=data).text
                logger.debug('added package pid: {}', pid)

                # Set Folder
                folder = config.get('folder', self.DEFAULT_FOLDER)
                folder = entry.get('path', folder)
                if folder:
                    # If folder has jinja template, render it
                    try:
                        folder = entry.render(folder)
                    except RenderError as e:
                        folder = self.DEFAULT_FOLDER
                        logger.error('Error rendering jinja event: {}', e)
                    # set folder with api
                    data = json.dumps({folder_key: folder})
                    post_data = {package_id_parameter: pid, 'data': data}
                    if not is_pyload_ng:
                        post_data['session'] = session
                    api.post(set_package_data_command, data=post_data)

                # Set Package Password
                package_password = config.get('package_password')
                if package_password:
                    data = json.dumps({'password': package_password})
                    post_data = {package_id_parameter: pid, 'data': data}
                    if not is_pyload_ng:
                        post_data['session'] = session
                    api.post(set_package_data_command, data=post_data)

            except Exception as e:
                entry.fail(str(e))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPyLoad, 'pyload', api_ver=2)
