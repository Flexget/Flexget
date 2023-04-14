from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

logger = logger.bind(name='kitsu')


class KitsuAnime:
    """
    Creates an entry for each item in your kitsu.io list.

    Syntax:

    kitsu:
      username: <value>
      user_id: <value>
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
            'user_id': {'type': 'string'},
            'lists': one_or_more(
                {
                    'type': 'string',
                    'enum': ['current', 'planned', 'completed', 'on_hold', 'dropped'],
                }
            ),
            'type': one_or_more(
                {'type': 'string', 'enum': ['ona', 'ova', 'tv', 'movie', 'music', 'special']}
            ),
            'latest': {'type': 'boolean', 'default': False},
            'status': {'type': 'string', 'enum': ['airing', 'finished']},
        },
        'oneOf': [{'required': ['username']}, {'required': ['user_id']}],
        'additionalProperties': False,
    }

    @cached('kitsu', persist='2 hours')
    def on_task_input(self, task, config):
        user_id = self._resolve_user_id(task, config)
        next_url = 'https://kitsu.io/api/edge/users/{user_id}/library-entries'.format(
            user_id=user_id
        )

        payload = {
            'filter[status]': ','.join(config['lists']),
            'filter[kind]': 'anime',
            'include': 'anime',
            'fields[anime]': 'canonicalTitle,titles,endDate,subtype',
            'fields[libraryEntries]': 'anime',
            'page[limit]': 20,
        }

        try:
            response = task.requests.get(next_url, params=payload)
        except RequestException as e:
            error_message = f'Error getting list from {e.request.url}'
            if hasattr(e, 'response'):
                error_message += f' status: {e.response.status_code}'
            logger.opt(exception=True).debug(error_message)
            raise plugin.PluginError(error_message)
        json_data = response.json()

        while json_data:
            anime_dict = {
                relation['id']: relation
                for relation in json_data['included']
                if relation['type'] == 'anime'
            }

            for item in json_data['data']:
                if item['relationships']['anime']['data'] is None:
                    logger.opt(exception=True).debug('Anime relation missing')
                    continue

                anime = anime_dict[item['relationships']['anime']['data']['id']]

                status = config.get('status')
                if status is not None:
                    if status == 'airing' and anime['attributes']['endDate'] is not None:
                        continue
                    if status == 'finished' and anime['attributes']['endDate'] is None:
                        continue

                types = config.get('type')
                if types is not None:
                    subType = anime['attributes']['subtype']
                    if subType is None or subType.lower() not in types:
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
                    yield entry

            next_url = json_data['links'].get('next')
            if next_url:
                try:
                    response = task.requests.get(next_url)
                except RequestException as e:
                    error_message = 'Error getting list from next page url: {url}'.format(
                        url=e.request.url
                    )
                    if hasattr(e, 'response'):
                        error_message += f' status: {e.response.status_code}'
                    logger.opt(exception=True).debug(error_message)
                    raise plugin.PluginError(error_message)
                json_data = response.json()
            else:
                break

    def _resolve_user_id(self, task, config):
        user_id = config.get('user_id')

        if user_id is None:
            user_payload = {'filter[name]': config['username']}
            try:
                user_response = task.requests.get(
                    'https://kitsu.io/api/edge/users', params=user_payload
                )
            except RequestException as e:
                error_message = f'Error finding User url: {e.request.url}'
                if hasattr(e, 'response'):
                    error_message += f' status: {e.response.status_code}'
                logger.opt(exception=True).debug(error_message)
                raise plugin.PluginError(error_message)
            user = user_response.json()
            if not len(user['data']):
                raise plugin.PluginError(
                    'no such username found "{name}"'.format(name=config['username'])
                )
            user_id = user['data'][0]['id']

        return user_id


@event('plugin.register')
def register_plugin():
    plugin.register(KitsuAnime, 'kitsu', api_ver=2)
