from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import xml.etree.ElementTree as ET

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

log = logging.getLogger('my_anime_list')
STATUS = {
    '1': 'watching',
    '2': 'completed',
    '3': 'on_hold',
    '4': 'dropped',
    '6': 'plan_to_watch',
}

ANIME_TYPE = {
    '0': 'unknown',
    '1': 'series',
    '2': 'ova',
    '3': 'movie',
    '4': 'special',
    '5': 'ona',
    '6': 'music'
}


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
            'status': one_or_more({'type': 'string', 'enum': list(STATUS.values())}, unique_items=True),
            'type': one_or_more({'type': 'string', 'enum': list(ANIME_TYPE.values())}, unique_items=True)
        },
        'required': ['username'],
        'additionalProperties': False
    }

    @cached('my_anime_list', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        parameters = {'u': config['username'], 'status': 'all', 'type': 'anime'}
        selected_status = config.get('status', list(STATUS.values()))
        selected_types = config.get('type', list(ANIME_TYPE.values()))

        if not isinstance(selected_status, list):
            selected_status = [selected_status]

        if not isinstance(selected_types, list):
            selected_types = [selected_types]

        try:
            list_response = task.requests.get('https://myanimelist.net/malappinfo.php', params=parameters)
        except RequestException as e:
            raise plugin.PluginError('Error finding list on url: {url}'.format(url=e.request.url))

        try:
            tree = ET.fromstring(list_response.text.encode('utf-8'))
            list_items = tree.findall('anime')
        except ET.ParseError:
            raise plugin.PluginError('Bad XML')

        for item in list_items:
            my_anime_list_id = item.findtext('series_animedb_id')
            title = item.findtext('series_title').strip()
            anime_type = ANIME_TYPE[item.findtext('series_type', 1)]
            my_status = STATUS[item.findtext('my_status')]

            my_tags = []
            alternate_names = []
            is_exact = False

            for name in item.findtext('series_synonyms', '').split('; '):
                stripped = name.strip()
                if stripped and stripped is not title:
                    alternate_names.append(name)

            for tag in item.findtext('my_tags', '').split(','):
                stripped = tag.strip()
                if stripped:
                    my_tags.append(stripped)
                    if stripped is 'exact':
                        is_exact = True

            # if user has chosen a status or a type, match strictly, otherwise let it all through
            wanted_status = not selected_status or my_status in selected_status
            wanted_type = not selected_types or anime_type in selected_types

            if wanted_status and wanted_type:
                entry = Entry(title=title,
                              url='https://myanimelist.net/anime/{}'.format(my_anime_list_id),
                              configure_series_alternate_name=alternate_names,
                              my_anime_list_type=anime_type,
                              my_anime_list_status=my_status,
                              my_anime_list_tags=my_tags)

                if is_exact:
                    entry['configure_series_exact'] = True

                if entry.isvalid():
                    entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(MyAnimeList, 'my_anime_list', api_ver=2)
