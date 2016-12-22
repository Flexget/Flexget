from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
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
      list_only: <airing|finished>
      latest: <yes|no>
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'lists': one_or_more({'type': 'string', 'enum': ['current', 'planned', 'completed', 'on_hold', 'dropped']}),
            'latest': {'type': 'boolean', 'default': False},
            'limit_to': {'type': 'string', 'enum': ['airing', 'finished']}
        },
        'required': ['username'],
        'additionalProperties': False,
    }

    @cached('kitsu', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        user_payload = {'filter[name]': config['username']}
        try:
            user_response = task.requests.get('https://kitsu.io/api/edge/users', params=user_payload)
            user_response.raise_for_status()
        except RequestException as e:
            error_message = 'Error finding User url: {url} status: {status}'.format(
                url=e.request.url, status=e.response.status_code)
            log.debug(error_message, exc_info=True)
            raise plugin.PluginError(error_message)
        user = user_response.json()
        if len(user['data']) < 1:
            raise plugin.PluginError('no such username found "{name}"'.format(name=config['username']))
        next_url = 'https://kitsu.io/api/edge/users/{id}/library-entries'.format(id=user['data'][0]['id'])
        payload = {'filter[status]': ','.join(config['lists']), 'filter[media_type]': 'Anime', 'include': 'media',
                   'page[limit]': 20}
        try:
            response = task.requests.get(next_url, params=payload)
            response.raise_for_status()
        except RequestException as e:
            error_message = 'Error getting list from {url} status: {status}'.format(
                url=e.request.url, status=e.response.status_code)
            log.debug(error_message, exc_info=True)
            log.info(error_message, exc_info=True)
            raise plugin.PluginError(error_message)

        while response:
            json_data = response.json()

            for item, anime in zip(json_data['data'], json_data['included']):
                if item['relationships']['media']['data']['id'] != anime['id']:
                    raise ValueError(
                        'Anime IDs {id1} and {id2} do not match'.format(
                            id1=item['relationships']['media']['data']['id'], id2=anime['id']))
                limit_to = config.get('limit_to')
                if limit_to is not None:
                    if limit_to == 'airing' and anime['attributes']['endDate'] is not None:
                        continue
                    if limit_to == 'finished' and anime['attributes']['endDate'] is None:
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
                except RequestException as e:
                    error_message = 'Error getting list from next page url: {url} status: {status}'.format(
                        url=e.request.url, status=e.response.status_code)
                    log.debug(error_message, exc_info=True)
                    raise plugin.PluginError(error_message)
            else:
                response = None

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(KitsuAnime, 'kitsu', api_ver=2)
