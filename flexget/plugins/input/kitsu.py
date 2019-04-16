from __future__ import unicode_literals, division, absolute_import

import logging


from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

log = logging.getLogger('kitsu')


class KitsuAnime(object):
    """
    Creates an entry for each item in your kitsu.io list.

    Syntax:

    kitsu:
      username: <value>
      lists:
        - <current|planned|completed|on_hold|dropped>
        - <current|planned|completed|on_hold|dropped>
      type:
        - <ona|ova|tv|movie|music|special>
        - <ona|ova|tv|movie|music|special>
      status: <airing|finished>
      latest: <yes|no>
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'lists': one_or_more(
                {
                    'type': 'string',
                    'enum': ['current', 'planned', 'completed', 'on_hold', 'dropped'],
                }
            ),
            'type': one_or_more(
                {
                    'type': 'string',
                    'enum': ['ona', 'ova', 'tv', 'movie', 'music', 'special'],
                }
            ),
            'latest': {'type': 'boolean', 'default': False},
            'status': {'type': 'string', 'enum': ['airing', 'finished']},
        },
        'required': ['username'],
        'additionalProperties': False,
    }

    @cached('kitsu', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        user_payload = {'filter[name]': config['username']}
        try:
            user_response = task.requests.get(
                'https://kitsu.io/api/edge/users', params=user_payload
            )
        except RequestException as e:
            error_message = 'Error finding User url: {url}'.format(url=e.request.url)
            if hasattr(e, 'response'):
                error_message += ' status: {status}'.format(status=e.response.status_code)
            log.debug(error_message, exc_info=True)
            raise plugin.PluginError(error_message)
        user = user_response.json()
        if not len(user['data']):
            raise plugin.PluginError(
                'no such username found "{name}"'.format(name=config['username'])
            )
        next_url = 'https://kitsu.io/api/edge/users/{id}/library-entries'.format(
            id=user['data'][0]['id']
        )
        payload = {
            'filter[status]': ','.join(config['lists']),
            'filter[media_type]': 'Anime',
            'include': 'media',
            'page[limit]': 20,
        }
        try:
            response = task.requests.get(next_url, params=payload)
        except RequestException as e:
            error_message = 'Error getting list from {url}'.format(url=e.request.url)
            if hasattr(e, 'response'):
                error_message += ' status: {status}'.format(status=e.response.status_code)
            log.debug(error_message, exc_info=True)
            raise plugin.PluginError(error_message)

        json_data = response.json()

        while json_data:

            for item, anime in zip(json_data['data'], json_data['included']):
                if item['relationships']['media']['data']['id'] != anime['id']:
                    raise ValueError(
                        'Anime IDs {id1} and {id2} do not match'.format(
                            id1=item['relationships']['media']['data']['id'], id2=anime['id']
                        )
                    )
                status = config.get('status')
                if status is not None:
                    if status == 'airing' and anime['attributes']['endDate'] is not None:
                        continue
                    if status == 'finished' and anime['attributes']['endDate'] is None:
                        continue

                types = config.get('type')
                if types is not None:
                    subType = anime['attributes']['subtype']
                    if subType is None or not subType.lower() in types:
                        continue
                    
                entry = Entry()
                entry['title'] = anime['attributes']['canonicalTitle']
                titles_en = anime['attributes']['titles'].get('en')
                if titles_en:
                    entry['kitsu_title_en'] = titles_en
                titles_en_jp = anime['attributes']['titles'].get('en_jp')
                if titles_en_jp:
                    entry['kitsu_title_en_jp'] = titles_en_jp
                titles_ja_jp = anime['attributes']['titles'].get('ja_jp')
                if titles_ja_jp:
                    entry['kitsu_title_ja_jp'] = titles_ja_jp
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
                except RequestException as e:
                    error_message = 'Error getting list from next page url: {url}'.format(
                        url=e.request.url
                    )
                    if hasattr(e, 'response'):
                        error_message += ' status: {status}'.format(status=e.response.status_code)
                    log.debug(error_message, exc_info=True)
                    raise plugin.PluginError(error_message)
                json_data = response.json()
            else:
                break

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(KitsuAnime, 'kitsu', api_ver=2)
