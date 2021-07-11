from loguru import logger
from requests import Session
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from requests import Session
from loguru import logger

from flexget.entry import Entry
from flexget.task import Task

logger = logger.bind(name='flood')

class FloodClient:
    def __init__(self):
        self.session = Session()
        self.connected = False

    def _request(self, method: str, path: str, **kwargs):
        try:
            return self.session.request(method, self.url + path, **kwargs)
        except RequestException as e:
            raise plugin.PluginError(f'Flood Request Exception: {e}')
    
    def authenticate(self, config):
        self.url = config['url'].strip('/')

        response = self._request('post', '/api/auth/authenticate', data={
            'username': config['username'],
            'password': config['password']
        })

        if response.status_code == 200:
            self.connected = True
            logger.debug('Successfully logged into Flood')
        else:
            self.connected = False
            raise plugin.PluginError('Incorrect username or password')

        return self
    
    def add_torrent_urls(self, **kwargs):
        if not self.connected:
            raise plugin.PluginError('Flood is not connected.')

        # Add's a default 'start': True to the request
        if not kwargs.get('start'):
            kwargs['start'] = True
        
        response = self._request('post', '/api/torrents/add-urls', json=kwargs)

        if response.status_code == 200:
            logger.debug('Successfully added torrent(s).')
        else:
            # There's no sanity to the codes returned by Flood. 
            # Both return "code": -32602 and both return status 500.
            if response.text.find('the input is not a valid.') > 0:
                raise plugin.PluginError('Not a valid torrent.')
            elif response.text.find('Info hash already used by another torrent.') > 0:
                logger.debug('Torrent has already been added to Flood.')
            else:
                raise plugin.PluginError(f'Failed to add torrent to Flood. Error {response.status_code}.')
    
    def add_torrent_files(self,  **kwargs):
        return False

class OutputFlood:
    schema = {
       'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'path': {'type': 'string'},
            'tags': {'type': 'array'},
        },
        'additionalProperties': False,
    }

    def add_entry(self, config: dict, task: Task, entry: Entry):
        kwargs = {}

        url = entry.get('url', None)
        path = entry.get('path', config.get('path', None))
        tags = entry.get('tags', config.get('tags', None))

        if url:
            kwargs['urls'] = [ url ]
        if path: 
            kwargs['destination'] = path
        # Because of the way that Flood wants things
        # We've gotta check to see if the person has done 
        # a list in their config or not.
        if tags:
            if isinstance(tags, list):
                kwargs['tags'] = tags
            else:
                kwargs['tags'] = [ tags ]

        if task.manager.options.test:
            logger.info('Flood Test Mode')
            logger.info('Would add torrent to Flood with:')
            logger.info('\tPath: {}', path)
            logger.info('\tTags: {}', tags)
        else:
            self.flood.add_torrent_urls(**kwargs)

    @plugin.priority(135)
    def on_task_output(self, task: Task, config: dict):
        # If we don't have any accepted entries, then let's just stop (possibly redundant?)
        if not task.accepted:
            return

        # We're re-authenticating ourselves every time we output
        self.flood = FloodClient().authenticate(config)

        # Loop through each accepted entry and send it to Flood
        for entry in task.accepted:
            self.add_entry(config, task, entry)

@event('plugin.register')
def register_plugin():
    plugin.register(OutputFlood, 'flood', api_ver=2)
