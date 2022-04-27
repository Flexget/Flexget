from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

logger = logger.bind(name='my_anime_list')

STATUS = {'watching': 1, 'completed': 2, 'on_hold': 3, 'dropped': 4, 'plan_to_watch': 6, 'all': 7}

AIRING_STATUS = {'airing': 1, 'finished': 2, 'planned': 3, 'all': 6}

ANIME_TYPE = ['all', 'tv', 'ova', 'movie', 'special', 'ona', 'music', 'unknown']


class MyAnimeList:
    """ " Creates entries for series and movies from MyAnimeList list

    Syntax:
    my_anime_list:
      username: <value>
      status:
        - <watching|completed|on_hold|dropped|plan_to_watch>
        - <watching|completed|on_hold|dropped|plan_to_watch>
        ...
      airing_status:
        - <airing|finished|planned>
        - <airing|finished|planned>
        ...
      type:
        - <series|ova...>
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'status': one_or_more(
                {'type': 'string', 'enum': list(STATUS.keys()), 'default': 'all'},
                unique_items=True,
            ),
            'airing_status': one_or_more(
                {'type': 'string', 'enum': list(AIRING_STATUS.keys()), 'default': 'all'},
                unique_items=True,
            ),
            'type': one_or_more(
                {'type': 'string', 'enum': list(ANIME_TYPE), 'default': 'all'}, unique_items=True
            ),
        },
        'required': ['username'],
        'additionalProperties': False,
    }

    @cached('my_anime_list', persist='2 hours')
    def on_task_input(self, task, config):
        selected_status = config.get('status', ['all'])
        if not isinstance(selected_status, list):
            selected_status = [selected_status]

        selected_airing_status = config.get('airing_status', ['all'])
        if not isinstance(selected_airing_status, list):
            selected_airing_status = [selected_airing_status]

        selected_types = config.get('type', ['all'])
        if not isinstance(selected_types, list):
            selected_types = [selected_types]

        selected_status = [STATUS[s] for s in selected_status]
        selected_airing_status = [AIRING_STATUS[s] for s in selected_airing_status]
        list_json = []

        for status in selected_status:
            # JSON pages are limited to 300 entries
            offset = 0
            results = 300
            while results == 300:
                try:
                    list_json += task.requests.get(
                        f'https://myanimelist.net/animelist/{config.get("username")}/load.json',
                        params={'status': status, 'offset': offset},
                    ).json()
                except RequestException as e:
                    logger.error(f'Error finding list on url: {e.request.url}')
                    break
                except (ValueError, TypeError):
                    logger.error('Invalid JSON response')
                    break
                results = len(list_json) or 1
                offset += len(list_json)

            for anime in list_json:
                has_selected_status = (
                    anime["status"] in selected_status or config['status'] == 'all'
                )
                has_selected_airing_status = (
                    anime["anime_airing_status"] in selected_airing_status
                    or config['airing_status'] == 'all'
                )
                has_selected_type = (
                    anime["anime_media_type_string"].lower() in selected_types
                    or config['type'] == 'all'
                )
                if has_selected_status and has_selected_type and has_selected_airing_status:
                    # MAL sometimes returns title as an integer
                    anime['anime_title'] = str(anime['anime_title'])
                    entry = Entry()
                    entry['title'] = anime['anime_title']
                    entry['url'] = f'https://myanimelist.net{anime["anime_url"]}'
                    entry['mal_name'] = anime['anime_title']
                    entry['mal_poster'] = anime['anime_image_path']
                    entry['mal_type'] = anime['anime_media_type_string']
                    entry['mal_tags'] = anime['tags']
                    if entry.isvalid():
                        yield entry


@event('plugin.register')
def register_plugin():
    plugin.register(MyAnimeList, 'my_anime_list', api_ver=2)
