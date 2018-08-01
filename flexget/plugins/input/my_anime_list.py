from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

log = logging.getLogger('my_anime_list')

STATUS = {
    'watching': 1,
    'completed': 2,
    'on_hold': 3,
    'dropped': 4,
    'plan_to_watch': 6,
    'all': 7
}

ANIME_TYPE = [
    'all',
    'tv',
    'ova',
    'movie',
    'special',
    'ona',
    'music',
    'unknown'
]

class MyAnimeList(object):
    """" Creates entries for series and movies from MyAnimeList list
    Syntax:
    my_anime_list:
      username: <value>
      status:
        - <watching|completed|on_hold|dropped|plan_to_watch>
        - <watching|completed|on_hold|dropped|plan_to_watch>
        ...
      type:
        - <series|ova...>
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'status': one_or_more({'type': 'string', 'enum': list(STATUS.keys()), 'default': 'all'}, unique_items=True),
            'type': one_or_more({'type': 'string', 'enum': list(ANIME_TYPE), 'default': 'all'}, unique_items=True)
        },
        'required': ['username'],
        'additionalProperties': False
    }

    @cached('my_anime_list', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        selected_status = config['status']
        selected_types = config['type']

        if not isinstance(selected_status, list):
            selected_status = [selected_status]

        if not isinstance(selected_types, list):
            selected_types = [selected_types]

        selected_status = [STATUS[s] for s in selected_status]

        try:
            list_response = task.requests.get('https://myanimelist.net/animelist/' + config['username'] + '/load.json')
        except RequestException as e:
            raise plugin.PluginError('Error finding list on url: {url}'.format(url=e.request.url))

        try:
            list_json = list_response.json()
        except ValueError:
            raise plugin.PluginError('Invalid JSON response')

        for anime in list_json:
            has_selected_status = anime["status"] in selected_status or config['status'] == 'all'
            has_selected_type = anime["anime_media_type_string"].lower() in selected_types or config['type'] == 'all'
            if has_selected_status and has_selected_type:
                entries.append(
                    Entry(
                        title=anime["anime_title"],
                        url="https://myanimelist.net" + anime["anime_url"],
                        mal_name=anime["anime_title"],
                        mal_poster=anime["anime_image_path"],
                        mal_type=anime["anime_media_type_string"]
                    )
                )
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(MyAnimeList, 'my_anime_list', api_ver=2)
