from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from requests import RequestException

log = logging.getLogger('kitsu')


class KitsuAnime(object):
    """Creates an entry for each item in your kitsu.io list.
    Syntax:
    kitsu:
      username: <value>
      lists:
      	- <current|planned|completed|on_hold|dropped>
      	- <current|planned|completed|on_hold|dropped>
      latest: <yes|no>
      finishedonly: <yes|no>
      currentonly: <yes|no>
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'lists': {'type': 'array',
                      'items': {'type': 'string', 'enum': ['current', 'planned', 'completed', 'on_hold', 'dropped']}},
            'latest': {'type': 'boolean', 'default': False},
            'currentonly': {'type': 'boolean', 'default': False},
            'finishedonly': {'type': 'boolean', 'default': False}
        },
        'required': ['username'],
        'additionalProperties': False,
    }

    @cached('kitsu', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        try:
            user_payload = {'filter[name]': config['username']}
            user_response = task.requests.get('https://kitsu.io/api/edge/users', params=user_payload)
            user_response.raise_for_status()
            user = user_response.json()
            if len(user['data']) < 1:
                raise plugin.PluginError('no such username found on kitsu.io')
            userId = user['data'][0]['id']
        except RequestException:
            raise plugin.PluginError('Error getting User ID from kitsu.io')

        next_url = 'https://kitsu.io/api/edge/users/{userId}/library-entries'.format(**locals())
        payload = {'filter[status]': ','.join(config['lists']), 'filter[media_type]': 'Anime', 'include': 'media',
                   'page[limit]': 20}

        try:
            response = task.requests.get(next_url, params=payload)
            response.raise_for_status()
        except RequestException:
            raise plugin.PluginError('Error getting list from kitsu.io')

        while response:
            json_data = response.json()

            for item, anime in zip(json_data['data'], json_data['included']):
                if item['relationships']['media']['data']['id'] != anime['id']:
                    raise ValueError
                if config.get('finishedonly') and anime['attributes']['endDate'] == None:
                    continue
                if config.get('currentonly') and anime['attributes']['endDate'] is not None:
                    continue

                entry = Entry()
                entry['title'] = anime['attributes']['canonicalTitle']
                if anime['attributes']['titles']['en']:
                    entry['kitsu_title_en'] = anime['attributes']['titles']['en']
                if anime['attributes']['titles']['en_jp']:
                    entry['kitsu_title_en_jp'] = anime['attributes']['titles']['en_jp']
                if anime['attributes']['titles']['ja_jp']:
                    entry['kitsu_title_ja_jp'] = anime['attributes']['titles']['ja_jp']
                entry['url'] = anime['links']['self']
                if entry.isvalid():
                    if config.get('latest'):
                        entry['series_episode'] = item['progress']
                        entry['series_id_type'] = 'sequence'
                        entry['title'] += ' ' + str(entry['progress'])
                    entries.append(entry)

            next_url = json_data['links'].get('next')
            if next_url:
                try:
                    response = task.requests.get(next_url)
                    response.raise_for_status()
                except RequestException:
                    raise plugin.PluginError('Error getting next url from kitsu.io')
            else:
                response = None

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(KitsuAnime, 'kitsu', api_ver=2)
