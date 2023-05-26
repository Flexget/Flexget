from urllib.parse import urlparse

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='medusa')


class Medusa:
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string', 'format': 'uri'},
            'port': {'type': 'number', 'default': 8081},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'only_monitored': {'type': 'boolean', 'default': False},
            'include_ended': {'type': 'boolean', 'default': False},
        },
        'required': ['username', 'password', 'base_url'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        """
        This plugin returns ALL of the shows monitored by Medusa.
        This includes both ongoing and ended.
        Syntax:

        medusa:
          base_url=<value>
          port=<value>
          username=<value>
          password=<value>

        Options base_url, username and password are required.

        Use with input plugin like discover and/or configure_series.
        Example:

        download-tv-task:
          configure_series:
            from:
              medusa:
                base_url: http://localhost
                port: 8531
                username: USERNAME
                password: PASSWORD
          discover:
            what:
              - next_series_episodes: yes
            from:
              torrentz: any
          download:
            /download/tv

        Note that when using the configure_series plugin with Medusa
        you are basically synced to it, so removing a show in Medusa will
        remove it in flexget as well, which could be positive or negative,
        depending on your usage.
        """
        parsed_url = urlparse(config.get('base_url'))
        base_url = '{scheme}://{url}:{port}/api/v2'.format(
            scheme=parsed_url.scheme, url=parsed_url.netloc, port=config.get('port')
        )

        body_auth = {'username': config.get('username'), 'password': config.get('password')}

        api_key = task.requests.post(f'{base_url}/authenticate', json=body_auth).json()['token']

        headers = {'x-auth': 'Bearer ' + api_key}

        params = {'limit': 1000}

        series = task.requests.get(f'{base_url}/series', params=params, headers=headers).json()

        entries = []
        for show in series:
            logger.debug('processing show: {}', show)
            if (
                (show['config']['paused'] and config.get('only_monitored'))
                or show['status'] == 'Ended'
                and not config.get('include_ended')
            ):
                logger.debug('discarted show: {}', show)

            entry = Entry(title=show['title'], url='', series_name=show['title'])

            if entry.isvalid():
                entries.append(entry)
            else:
                logger.error(f'Invalid entry created? {entry}')

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Medusa, 'medusa', api_ver=2)
