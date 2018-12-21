from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse

import logging
import json

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('medusa')


class Medusa(object):
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 8081},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'only_monitored': {'type': 'boolean', 'default': False},
            'include_ended': {'type': 'boolean', 'default': False},
        },
        'required': ['username', 'password', 'base_url'],
        'additionalProperties': False
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8'
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
            scheme=parsed_url.scheme,
            url=parsed_url.netloc,
            port=config.get('port'),
        )

        body_auth = dict(
            username=config.get('username'),
            password=config.get('password'),
        )

        try:
            api_key = json.loads(task.requests.post(
                '{}/authenticate'.format(base_url),
                data=json.dumps(body_auth),
                headers=self.headers
            ).content.decode('utf-8'))['token']

            self.headers.update(
                authorization='Bearer ' + api_key
            )

            series = json.loads(task.requests.get(
                '{}/series?limit=1000'.format(base_url),
                headers=self.headers
            ).content.decode('utf-8'))
        except RequestException as e:
            raise plugin.PluginError(
                'Unable to get series in Medusa at {}://{}:{}{}. Error: {}'.format(
                    parsed_url.scheme, parsed_url.netloc, config.get('port'), parsed_url.path, e)
            )

        entries = []
        for show in series:
            log.debug('processing show: {}'.format(show))
            if (show['config']['paused'] and config.get('only_monitored')) or \
                    show['status'] == 'Ended' and not config.get('include_ended'):
                continue

            entry = Entry(title=show['title'],
                          url='',
                          series_name=show['title'])

            if entry.isvalid():
                entries.append(entry)
            else:
                log.error('Invalid entry created? {}'.format(entry))
                continue

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Medusa, 'medusa', api_ver=2)
