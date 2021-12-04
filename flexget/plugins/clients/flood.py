from datetime import datetime

from loguru import logger
from requests import Session
from requests.exceptions import RequestException
from sqlalchemy import Column, DateTime, String, Unicode

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.task import Task
from flexget.utils.database import json_synonym

logger = logger.bind(name='flood')
Base = versioned_base('flood_session', 0)


class FloodSession(Base):
    __tablename__ = 'flood_session'

    url = Column(String, primary_key=True)
    username = Column(Unicode, primary_key=True)

    _cookies = Column('cookie', Unicode)
    cookies = json_synonym('_cookies')
    expires = Column(DateTime)


class FloodClient:
    def __init__(self, config: dict):
        self.config = config
        self.session = Session()
        self.connected = False

    def _request(self, method: str, path: str, **kwargs):
        if not self.connected and path != '/api/auth/authenticate':
            raise plugin.PluginError('Flood is not connected.')

        try:
            return self.session.request(method, self.config['url'].strip('/') + path, **kwargs)
        except RequestException as e:
            raise plugin.PluginError(f'Flood Request Exception: {e}')

    @with_session
    def _save_session(self, session=None):
        logger.debug('Saving session')

        expires = next(x for x in self.session.cookies if x.name == 'jwt').expires
        if not expires:
            raise plugin.PluginError('Expires cannot be None')

        flood_session = FloodSession(
            url=self.config['url'].strip('/'),
            username=self.config['username'],
            cookies=dict(self.session.cookies),
            expires=datetime.utcfromtimestamp(expires),
        )

        session.merge(flood_session)
        logger.debug('Saved session')

    @with_session
    def _restore_session(self, session=None):
        logger.debug('Looking for saved session')

        flood_session = (
            session.query(FloodSession).filter(
                FloodSession.url == self.config['url'].strip('/'),
                FloodSession.username == self.config['username'],
            )
        ).one_or_none()

        if flood_session and flood_session.expires > datetime.utcnow():
            self.session.cookies.update(flood_session.cookies)
            logger.debug('Found saved session')
            return True

        logger.debug('Unable to find saved session')
        return False

    def authenticate(self):
        if self._restore_session():
            self.connected = True
            return self

        response = self._request(
            'post',
            '/api/auth/authenticate',
            data={'username': self.config['username'], 'password': self.config['password']},
        )

        if response.status_code == 200:
            self._save_session()
            self.connected = True
            logger.debug('Successfully logged into Flood')
        else:
            self.connected = False
            raise plugin.PluginError('Incorrect username or password')

        return self

    def add_torrent_urls(
        self, urls: list = None, destination: str = None, tags: list = None, start: bool = True
    ):
        if not urls:
            raise plugin.PluginError('Parameter urls cannot be empty.')

        data = {
            'urls': urls,
            'start': start,
        }

        if destination:
            data['destination'] = destination
        if tags:
            data['tags'] = tags

        response = self._request('post', '/api/torrents/add-urls', json=data)

        if response.status_code == 200:
            logger.debug('Successfully added torrent(s).')
        else:
            # There's no sanity to the codes returned by Flood.
            # Both return 'code': -32602 and both return status 500.
            if response.text.find('the input is not a valid.') > 0:
                raise plugin.PluginError('Not a valid torrent.')
            elif response.text.find('Info hash already used by another torrent.') > 0:
                logger.debug('Torrent has already been added to Flood.')
            else:
                raise plugin.PluginError(
                    f'Failed to add torrent to Flood. Error {response.status_code}.'
                )


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

    def add_entry(self, client: FloodClient, config: dict, task: Task, entry: Entry):
        url = entry.get('url', None)
        path = entry.render(entry.get('path', config.get('path', '')))
        tags = entry.get('tags', config.get('tags', None))

        if tags and isinstance(tags, list):
            tags = (
                [entry.render(tag) for tag in tags]
                if isinstance(tags, list)
                else [entry.render(tags)]
            )

        if task.manager.options.test:
            logger.info('Flood Test Mode')
            logger.info('Would add torrent to Flood with:')
            logger.info('\tPath: {}', path)
            logger.info('\tTags: {}', tags)
        else:
            client.add_torrent_urls(urls=[url], destination=path, tags=tags)

    @plugin.priority(135)
    def on_task_output(self, task: Task, config: dict):
        # If we don't have any accepted entries, then let's just stop (possibly redundant?)
        if not task.accepted:
            return

        flood = FloodClient(config).authenticate()

        # Loop through each accepted entry and send it to Flood
        for entry in task.accepted:
            self.add_entry(flood, config, task, entry)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputFlood, 'flood', api_ver=2)
