import base64
import os
import time
import urllib.parse

from loguru import logger
from requests import Response
from requests.exceptions import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import DependencyError, PluginError
from flexget.task import Task

try:
    from jwt import decode

    imported = True
except ImportError:
    imported = False

logger = logger.bind(name='flood')


class FloodClient:
    @staticmethod
    def request(task: Task, config: dict, method: str, url: str, success_list: list, **kwargs) -> Response:
        """
        Send a request to Flood.
        Returns None if the response status_code is not in the success_list.
        """

        try:
            response = task.requests.request(method, urllib.parse.urljoin(config["url"], url), **kwargs)
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to send a request to Flood: {e}")

        if not response.status_code in success_list:
            raise PluginError(f"Failed to send request to Flood. Received status {response.status_code} expected one of {success_list}.")
        
        return response

    @staticmethod
    def is_jwt_expired(task: Task) -> bool:
        """
        Check if the JWT token is expired.
        Returns True if the JWT token is expired or if the JWT token is not set.
        """

        jwt = task.requests.cookies.get('jwt')

        if not jwt:
            return True

        try:
            decoded_jwt = decode(jwt, algorithms="HS256", options={"verify_signature": False})
        except:
            return True

        return decoded_jwt.get("exp", 0) <= time.time()

    @staticmethod
    def authenticate(task: Task, config: dict) -> None:
        """
        Authenticate with Flood and obtain a JWT token.
        """

        # Attempt to authenticate with Flood.
        FloodClient.request(task, config, "post", "api/auth/authenticate", success_list=[200], json={"username": config["username"], "password": config["password"]})

        # Check if the JWT token is expired or unset.
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Failed to authenticate with Flood. No valid JWT was found.")
        
        logger.debug("Successfully authenticated with Flood.")

    @staticmethod
    def add_torrent_urls(
        task: Task,
        config: dict,
        urls: list,
        destination: str = None,
        tags: list = None,
        start: bool = True,
    ) -> None:
        """
        Add a list of torrent URLs to Flood.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if not urls:
            raise PluginError("Parameter 'urls' cannot be empty.")
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        data = {"urls": urls, "start": start}

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags

        # Attempt to add the torrent URLs to Flood.
        response = FloodClient.request(task, config, "post", "api/torrents/add-urls", success_list=[200, 202], json=data)
        
        # Check if the number of hashes returned by Flood matches the number of URLs.
        if len(response.json()) != len(urls):
            raise PluginError("Failed to add torrent URLs to Flood. Received a different number of hashes than the number of URLs.")

        logger.debug("Successfully added urls to Flood.")

    @staticmethod
    def add_torrent_files(
        task: Task,
        config: dict,
        files: list,
        destination: str = None,
        tags: list = None,
        start: bool = True,
    ) -> None:
        """
        Add a list of torrent files to Flood.
        Each file must be in base64 encoded format.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if not files:
            raise PluginError("Parameter 'urls' cannot be empty.")
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        data = {"files": files, "start": start}

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags

        # Attempt to add the torrent files to Flood.
        response = FloodClient.request(task, config, "post", "api/torrents/add-files", success_list=[200, 202], json=data)

        # Check if the number of hashes returned by Flood matches the number of files.
        if len(response.json()) != len(files):
            raise PluginError("Failed to add torrent files to Flood. Received a different number of hashes than the number of files.")
        
        logger.debug("Successfully added files to Flood.")

    @staticmethod
    def list_torrents(task: Task, config: dict) -> dict:
        """
        List all torrents in Flood.
        Will only attempt to list torrents if the JWT token is not expired or unset.
        """

        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        # Attempt to list torrents in Flood.
        response = FloodClient.request(task, config, "get", "api/torrents", success_list=[200])

        data = response.json()

        # Check if the response contains a 'torrents' key.
        if 'torrents' not in data:
            raise PluginError("Failed to list torrents in Flood. Unable to find 'torrents' key in response.")
        
        logger.debug("Successfully listed torrents in Flood.")
        return data.get("torrents")

    @staticmethod
    def start_torrents(task: Task, config: dict, hashes: list) -> None:
        """
        Start a list of torrents in Flood.
        Will only attempt to start torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(task, config, "post", "api/torrents/start", success_list=[200], json={"hashes": hashes})
        logger.debug(f"Successfully started torrents in Flood.")

    @staticmethod
    def stop_torrents(task: Task, config: dict, hashes: list) -> None:
        """
        Stop a list of torrents in Flood.
        Will only attempt to stop torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(task, config, "post", "api/torrents/stop", success_list=[200], json={"hashes": hashes})
        logger.debug(f"Successfully stopped torrents in Flood.")

    @staticmethod
    def delete_torrents(task: Task, config: dict, hashes: list, deleteData: bool = False) -> None:
        """
        Delete a list of torrents in Flood.
        Will only attempt to delete torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(task, config, "post", "api/torrents/delete", success_list=[200], json={"hashes": hashes, "deleteData": deleteData})
        logger.debug(f"Successfully deleted torrents in Flood.")

class InputFlood:
    """Creates entries from torrents in Flood based

    Example:
        from_flood:
            url: http://localhost:3000
            username: username
            password: password
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
        },
        'additionalProperties': False,
        'required': ['url'],
    }

    def generate_entry(self, config: dict, torrent: dict) -> Entry:
        """
        Generate a task entry from a torrent in Flood.
        """

        entry = Entry(url='', title=torrent['name'])

        for key, value in torrent.items():
            entry['flood_' + key.lower()] = value

        return entry

    def on_task_input(self, task: Task, config: dict):
        if FloodClient.is_jwt_expired(task):
            logger.debug("JWT token is expired. Re-authenticating with Flood.")
            FloodClient.authenticate(task, config)

        entries = []
        torrents = FloodClient.list_torrents(task, config)

        for hash, torrent in torrents.items():
            entry = self.generate_entry(config, torrent)

            if entry:
                entries.append(entry)

        return entries


class OutputFlood:
    """Add, remove, delete, start, or stop torrents in Flood.

    Example:
        flood:
            url: http://localhost:3000
            username: username
            password: password
            path: /downloads/Flexget
            tags: Flexget
            action: add
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'action': {'type': 'string', 'enum': ['add', 'remove', 'delete', 'start', 'stop']},
            'path': {'type': 'string'},
            'tags': {'type': 'array', 'items': {'type': 'string'}},
        },
        'additionalProperties': False,
        'required': ['url', 'action'],
    }

    def _add_entry(self, task: Task, config: dict, entry: Entry) -> None:
        """
        Add an entry to Flood.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if FloodClient.is_jwt_expired(task):
            raise PluginError("Not authenticated with Flood.")

        destination: str = entry.render(entry.get('path', ''), config.get('path', ''))
        # Combines the tags from the entry and the config.
        # The tags from the entry will be prioritized.
        tags: list = entry.get('tags', []) + [
            tag for tag in config.get('tags', []) if not tag in entry.get('tags', [])
        ]
        tags = [entry.render(tag) for tag in tags]
        start: bool = entry.get('start', config.get('start', True))

        if task.manager.options.test:
            logger.info('Would add {} to Flood with options:', entry['title'])

            if entry.get('file'):
                logger.info('  File: {}', entry['file'])
            elif entry.get('url'):
                logger.info('  Url: {}', entry['url'])
            else:
                logger.info('  No URL or File found.')

            logger.info('  Destination: {}', destination)
            logger.info('  Tags: {}', ', '.join(tags) or 'None')
            logger.info('  Start: {}', config.get('start', True))
            return

        if entry.get('file'):
            if not os.path.exists(entry['file']):
                return entry.fail('Temp file not found.')

            with open(entry['file'], 'rb') as fs:
                encoded_file = base64.b64encode(fs.read()).decode('utf-8')

                try:
                    FloodClient.add_torrent_files(task, config, [encoded_file], destination, tags, start)
                except PluginError as e:
                    return entry.fail(e)

        elif entry.get('url'):
            try:
                FloodClient.add_torrent_urls(task, config, [entry['url']], destination, tags, start)
            except PluginError as e:
                return entry.fail(e)
        else:
            return entry.fail('No URL or File found.')

    @plugin.priority(120)
    def on_task_download(self, task: Task, config: dict):
        """
        Use the download plugin to get temp files for entry URLs.
        """

        if config['action'] == 'add' and 'download' not in task.config:
            download = plugin.get('download', self)
            download.get_temp_files(task)

    @plugin.priority(135)
    def on_task_output(self, task: Task, config: dict):
        if not imported:
            raise DependencyError('pyjwt', 'pyjwt', 'pyjwt is required for this plugin')

        # Don't do anything if no config provided
        if not isinstance(config, dict):
            return

        # Authenticate with Flood if not already authenticated.
        if FloodClient.is_jwt_expired(task):
            logger.debug("JWT token is expired. Re-authenticating with Flood.")
            FloodClient.authenticate(task, config)

        for entry in task.accepted:
            if config['action'] == 'add':
                self._add_entry(task, config, entry)
            elif 'flood_hash' in entry:
                if config['action'] == 'remove':
                    FloodClient.delete_torrents(task, config, [entry['flood_hash']], False)
                elif config['action'] == 'delete':
                    FloodClient.delete_torrents(task, config, [entry['flood_hash']], True)
                elif config['action'] == 'start':
                    FloodClient.start_torrents(task, config, [entry['flood_hash']])
                elif config['action'] == 'stop':
                    FloodClient.stop_torrents(task, config, [entry['flood_hash']])


@event('plugin.register')
def register_plugin():
    plugin.register(InputFlood, 'from_flood', api_ver=2)
    plugin.register(OutputFlood, 'flood', api_ver=2)
