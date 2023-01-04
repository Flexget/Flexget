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
    success_list = [200, 202]

    @staticmethod
    def request(task: Task, config: dict, method: str, url: str, **kwargs) -> Response:
        """
        Send a request to Flood.
        Returns None if the response status_code is not in the success_list.
        """

        try:
            response = task.requests.request(
                method, urllib.parse.urljoin(config["url"], url), **kwargs
            )
        except RequestException as e:
            raise PluginError(
                f"An error occurred while attempting to send a request to Flood: {e}"
            )

        if not response.status_code in FloodClient.success_list:
            raise PluginError(
                f"Failed to send request to Flood. Received status {response.status_code} expected one of {FloodClient.success_list}."
            )

        return response

    @staticmethod
    def is_jwt_invalid(task: Task) -> bool:
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
        FloodClient.request(
            task,
            config,
            "post",
            "api/auth/authenticate",
            json={"username": config["username"], "password": config["password"]},
        )

        # Check if the JWT token is expired or unset.
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Failed to authenticate with Flood. No valid JWT was found.")

        logger.debug("Successfully authenticated with Flood.")

    @staticmethod
    def download_torrent_contents(task: Task, config: dict, hash: str, to_path: str) -> None:
        """
        Download a torrents contents from Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        for file in FloodClient.list_torrent_contents(task, config, hash):
            full_path = os.path.join(to_path, file['path'])
            base_path = os.path.dirname(full_path)

            if not os.path.exists(base_path):
                os.makedirs(base_path)

            if os.path.exists(full_path):
                logger.warning(f"File {full_path} already exists. Skipping...")
                continue

            response = FloodClient.request(
                task,
                config,
                "get",
                f"api/torrents/{hash}/contents/{file['index']}/data",
                stream=True,
            )

            with open(full_path, "wb") as fs:
                for chunk in response.iter_content(chunk_size=1024):
                    fs.write(chunk)

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
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if not urls:
            raise PluginError("Parameter 'urls' cannot be empty.")
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        data = {"urls": urls, "start": start}

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags

        # Attempt to add the torrent URLs to Flood.
        response = FloodClient.request(task, config, "post", "api/torrents/add-urls", json=data)

        # Check if the number of hashes returned by Flood matches the number of URLs.
        if len(response.json()) != len(urls):
            raise PluginError(
                "Failed to add torrent URLs to Flood. Received a different number of hashes than the number of URLs."
            )

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
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        data = {"files": files, "start": start}

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags

        # Attempt to add the torrent files to Flood.
        response = FloodClient.request(task, config, "post", "api/torrents/add-files", json=data)

        # Check if the number of hashes returned by Flood matches the number of files.
        if len(response.json()) != len(files):
            raise PluginError(
                "Failed to add torrent files to Flood. Received a different number of hashes than the number of files."
            )

        logger.debug("Successfully added files to Flood.")

    @staticmethod
    def list_torrent_contents(task: Task, config: dict, hash: str) -> list:
        """
        List the contents of a torrent in Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        # Attempt to list the torrent contents in Flood.
        response = FloodClient.request(task, config, "get", f"api/torrents/{hash}/contents")

        data = response.json()

        logger.debug("Successfully listed torrent contents.")
        return data

    @staticmethod
    def list_torrents(task: Task, config: dict) -> dict:
        """
        List all torrents in Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        # Attempt to list torrents in Flood.
        response = FloodClient.request(task, config, "get", "api/torrents")

        data = response.json()

        # Check if the response contains a 'torrents' key.
        if 'torrents' not in data:
            raise PluginError(
                "Failed to list torrents in Flood. Unable to find 'torrents' key in response."
            )

        logger.debug("Successfully listed torrents in Flood.")
        return data.get("torrents")

    @staticmethod
    def start_torrents(task: Task, config: dict, hashes: list) -> None:
        """
        Start a list of torrents in Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(task, config, "post", "api/torrents/start", json={"hashes": hashes})
        logger.debug(f"Successfully started torrents in Flood.")

    @staticmethod
    def stop_torrents(task: Task, config: dict, hashes: list) -> None:
        """
        Stop a list of torrents in Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(task, config, "post", "api/torrents/stop", json={"hashes": hashes})
        logger.debug(f"Successfully stopped torrents in Flood.")

    @staticmethod
    def delete_torrents(task: Task, config: dict, hashes: list, deleteData: bool = False) -> None:
        """
        Delete a list of torrents in Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        FloodClient.request(
            task,
            config,
            "post",
            "api/torrents/delete",
            json={"hashes": hashes, "deleteData": deleteData},
        )
        logger.debug(f"Successfully deleted torrents in Flood.")


class InputFlood:
    """Creates entries from torrents in Flood based

    Example:
        from_flood:
            url: http://localhost:3000  # Required. Url for Flexget to connect to Flood.
            username: flexget           # Required. Username for authentication with Flood.
            password: password          # Required. Password for authentication with Flood.
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
        },
        'additionalProperties': False,
        'required': ['url', 'username', 'password'],
    }

    def generate_entry(self, config: dict, torrent: dict) -> Entry:
        """
        Generate a task entry from a torrent in Flood.
        """

        entry = Entry(
            url=urllib.parse.urljoin(
                config['url'], f"api/torrents/{torrent['hash']}/contents/all/data"
            ),
            title=torrent['name'],
        )

        for key, value in torrent.items():
            entry['flood_' + key.lower()] = value

        return entry

    def on_task_input(self, task: Task, config: dict):
        if FloodClient.is_jwt_invalid(task):
            logger.debug("'jwt' cookie is invalid. Re-authenticating with Flood.")
            FloodClient.authenticate(task, config)

        entries = []
        torrents = FloodClient.list_torrents(task, config)

        for hash, torrent in torrents.items():
            entry = self.generate_entry(config, torrent)

            if entry:
                entries.append(entry)

        return entries


class OutputFlood:
    """Add, remove, delete, download, start, or stop torrents in Flood.

    Example:
        flood:
            url: http://localhost:3000  # Required. Url for Flexget to connect to Flood.
            username: flexget           # Required. Username for authentication with Flood.
            password: password          # Required. Password for authentication with Flood.
            action: add                 # Required. The action to perform. Can be 'add', 'remove', 'delete', 'download', 'start', or 'stop'.
            path: /downloads            # If the action is set to 'add', the path is relative to the Flood download directory.
                                        # If the action is set to 'download', the path is on the local filesystem.
            tags: [ 'Flexget' ]         # If the action is set to 'add', the tags to add to the torrent.
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'action': {
                'type': 'string',
                'enum': ['add', 'remove', 'delete', 'download', 'start', 'stop'],
            },
            'path': {'type': 'string'},
            'tags': {'type': 'array', 'items': {'type': 'string'}},
        },
        'additionalProperties': False,
        'required': ['url', 'username', 'password', 'action'],
    }

    def _accepted_entry(self, task: Task, config: dict, entry: Entry) -> None:
        """
        Process an accepted entry.
        """
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
            elif config['action'] == 'download':
                self._download_entry(task, config, entry)

    def _add_entry_file(
        self, task: Task, config: dict, entry: Entry, destination: str, tags: list, start: bool
    ) -> None:
        """
        Process an entry to add to Flood by file.
        """

        if not os.path.exists(entry['file']):
            return entry.fail('Temp file not found.')

        with open(entry['file'], 'rb') as fs:
            encoded_file = base64.b64encode(fs.read()).decode('utf-8')

            try:
                FloodClient.add_torrent_files(
                    task, config, [encoded_file], destination, tags, start
                )
            except PluginError as e:
                return entry.fail(e)

    def _add_entry_url(
        self, task: Task, config: dict, entry: Entry, destination: str, tags: list, start: bool
    ) -> None:
        """
        Process an entry to add to Flood by URL.
        """

        try:
            FloodClient.add_torrent_urls(task, config, [entry['url']], destination, tags, start)
        except PluginError as e:
            return entry.fail(e)

    def _add_entry(self, task: Task, config: dict, entry: Entry) -> None:
        """
        Add an entry to Flood.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        destination: str = entry.render(entry.get('path', config.get('path', '')))
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
            self._add_entry_file(task, config, entry, destination, tags, start)
        elif entry.get('url'):
            self._add_entry_url(task, config, entry, destination, tags, start)
        else:
            return entry.fail('No URL or File found.')

    def _download_entry(self, task: Task, config: dict, entry: Entry) -> None:
        """
        Download the torrent contents for an entry.
        Requires a 'flood_hash' to be set on the entry.
        Requires a 'path' to be set on the config or on the entry.
        Requires a 'jwt' cookie on the tasks requests session to be valid.
        """

        if not 'flood_hash' in entry:
            entry.fail('No flood_hash found for entry.')

        if FloodClient.is_jwt_invalid(task):
            raise PluginError("Not authenticated with Flood.")

        path: str = entry.render(entry.get('path', config.get('path', '')))

        if not path:
            return entry.fail('No path found for entry or config')

        try:
            FloodClient.download_torrent_contents(task, config, entry['flood_hash'], path)
        except PluginError as e:
            entry.fail(e)

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
        if FloodClient.is_jwt_invalid(task):
            logger.debug("'jwt' cookie is invalid. Re-authenticating with Flood.")
            FloodClient.authenticate(task, config)

        # Process entries
        for entry in task.accepted:
            self._accepted_entry(task, config, entry)


@event('plugin.register')
def register_plugin():
    plugin.register(InputFlood, 'from_flood', api_ver=2)
    plugin.register(OutputFlood, 'flood', api_ver=2)
