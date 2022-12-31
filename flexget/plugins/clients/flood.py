
import time, os, base64

from loguru import logger
from requests import post, get
from requests.exceptions import RequestException

from flexget import plugin
from flexget.plugin import DependencyError, PluginError
from flexget.event import event
from flexget.entry import Entry
from flexget.task import Task

try:
    from jwt import decode
    imported = True
except ImportError:
    imported = False

logger = logger.bind(name='flood')


class FloodClient:
    def __init__(self) -> None:
        self.jwt = ""
    
    def is_jwt_expired(self) -> bool:
        """
        Check if the JWT token is expired.
        Returns True if the JWT token is expired or if the JWT token is not set.
        """

        if not self.jwt:
            return True

        try:
            decoded_jwt = decode(self.jwt, algorithms="HS256", options={"verify_signature": False})
        except:
            return True

        return decoded_jwt.get("exp", 0) <= time.time()

    def authenticate(self, config: dict) -> None:
        """
        Authenticate with Flood and obtain a JWT token.
        """
        
        try:
            response = post(f"{config['url']}/api/auth/authenticate", json={
                "username": config["username"],
                "password": config["password"]
            })

            if response.status_code == 200 and response.cookies.get("jwt"):
                self.jwt = response.cookies.get("jwt")
                logger.debug("Successfully authenticated with Flood.")
            else:
                raise PluginError(f"Failed to authenticate with Flood. (status={response.status_code})")
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to authenticate with Flood: {e}")
    
    def add_torrent_urls(self, config: dict, urls: list, destination: str = None, tags: list = None, start: bool = True) -> bool:
        """
        Add a list of torrent URLs to Flood.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if not urls:
            raise PluginError("Parameter 'urls' cannot be empty.")
        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        data = {
            "urls": urls,
            "start": start
        }

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags

        try:
            response = post(f"{config['url']}/api/torrents/add-urls", json=data, cookies={"jwt": self.jwt})

            if response.status_code == 200:
                logger.debug(f"Successfully added {len(urls)} urls to Flood.")
                return True

            logger.debug(f"Failed to add {len(urls)} urls to Flood. (status={response.status_code})")
            return False                        
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to add torrent urls to Flood: {e}")

    def add_torrent_files(self, config: dict, files: list, destination: str = None, tags: list = None, start: bool = True) -> bool:
        """
        Add a list of torrent files to Flood.
        Each file must be in base64 encoded format.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if not files:
            raise PluginError("Parameter 'urls' cannot be empty.")
        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        data = {
            "files": files,
            "start": start
        }

        if destination:
            data["destination"] = destination
        if tags:
            data["tags"] = tags
        
        try:
            response = post(f"{config['url']}/api/torrents/add-files", json=data, cookies={"jwt": self.jwt})

            if response.status_code == 200:
                logger.debug(f"Successfully added {len(files)} files to Flood.")
                return True

            logger.debug(f"Failed to add {len(files)} files to Flood. (status={response.status_code})")
            return False
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to add torrent files to Flood: {e}")

    def list_torrents(self, config: dict) -> dict:
        """
        List all torrents in Flood.
        Will only attempt to list torrents if the JWT token is not expired or unset.
        """

        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        try:
            response = get(f"{config['url']}/api/torrents", cookies={"jwt": self.jwt})

            if response.status_code == 200:
                return response.json().get("torrents", {})

            logger.debug(f"Failed to list torrents in Flood. (status={response.status_code})")
            return {}
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to list torrents in Flood: {e}")

    def start_torrents(self, config: dict, hashes: list) -> bool:
        """
        Start a list of torrents in Flood.
        Will only attempt to start torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        try:
            response = post(f"{config['url']}/api/torrents/start", data={"hashes": hashes }, cookies={ "jwt": self.jwt})

            if response.status_code == 200:
                logger.debug(f"Successfully started {len(hashes)} torrents in Flood.")
                return True

            logger.debug(f"Failed to start {len(hashes)} torrents in Flood. (status={response.status_code})")
            return False
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to start torrents in Flood: {e}")

    def stop_torrents(self, config: dict, hashes: list) -> bool:
        """
        Stop a list of torrents in Flood.
        Will only attempt to stop torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        try:
            response = post(f"{config['url']}/api/torrents/stop", data={"hashes": hashes }, cookies={ "jwt": self.jwt})

            if response.status_code == 200:
                logger.debug(f"Successfully stopped {len(hashes)} torrents in Flood.")
                return True

            logger.debug(f"Failed to stop {len(hashes)} torrents in Flood. (status={response.status_code})")
            return False
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to stop torrents in Flood: {e}")

    def delete_torrents(self, config: dict, hashes: list, deleteData: bool = False) -> bool:
        """
        Delete a list of torrents in Flood.
        Will only attempt to delete torrents if the JWT token is not expired or unset.
        """

        if not hashes:
            raise PluginError("Parameter 'hashes' cannot be empty.")
        if self.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        try:
            response = post(f"{config['url']}/api/torrents/delete", data={"hashes": hashes, 'deleteData': deleteData}, cookies={"jwt": self.jwt})

            if response.status_code == 200:
                logger.debug(f"Successfully deleted {len(hashes)} torrents from Flood.")
                return True

            logger.debug(f"Failed to delete {len(hashes)} torrents from Flood. (status={response.status_code})")
            return False
        except RequestException as e:
            raise PluginError(f"An error occurred while attempting to delete torrents from Flood: {e}")
    
class OutputFlood:
    schema = {
       'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'action': {'type': 'string', 'enum': ['add', 'remove', 'delete']},
            'path': {'type': 'string'},
            'tags': {'type': 'array', 'items': {'type': 'string'}},
        },
        'additionalProperties': False,
    }

    def __init__(self) -> None:
        self.flood = FloodClient()

    def add_entry(self, config: dict, task: Task, entry: Entry) -> None:
        """
        Add an entry to Flood.
        Will only attempt to add torrents if the JWT token is not expired or unset.
        """

        if self.flood.is_jwt_expired():
            raise PluginError("Not authenticated with Flood.")

        destination: str = entry.render(entry.get('path', ''), config.get('path', ''))
        # Combines the tags from the entry and the config.
        # The tags from the entry will be prioritized.
        tags: list = entry.get('tags', []) + [ tag for tag in config.get('tags', []) if not tag in entry.get('tags', []) ]
        tags = [ entry.render(tag) for tag in tags ]
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
                if not self.flood.add_torrent_files(config, files=[ encoded_file ], destination=destination, tags=tags, start=start):
                    return entry.fail('Failed to add file(s) to Flood.')
        elif entry.get('url'):
            if not self.flood.add_torrent_urls(config, urls=[ entry['url'] ], destination=destination, tags=tags, start=start):
                return entry.fail('Failed to add url(s) to Flood.')
        else:
            return entry.fail('No URL or File found.')

    @plugin.priority(120)
    def on_task_download(self, task: Task, config: dict):
        """
        Use the download plugin to get temp files for entry URLs.
        """

        if 'download' not in task.config:
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
        if self.flood.is_jwt_expired():
            logger.debug("JWT token is expired. Re-authenticating with Flood.")
            self.flood.authenticate(config)
        
        if config['action'] == 'add':
            for entry in task.accepted:
                self.add_entry(config, task, entry)

@event('plugin.register')
def register_plugin():
    plugin.register(OutputFlood, 'flood', api_ver=2)
