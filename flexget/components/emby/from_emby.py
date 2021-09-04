from loguru import logger

from flexget.components.emby.api_emby import EmbyAuth, EmbyApi, EmbyApiList
from flexget.config_schema import one_or_more
from flexget import plugin
from flexget.event import event
from flexget.components.emby.emby_util import SCHEMA_SERVER_TAG, SORT_FIELDS

logger = logger.bind(name='from_emby')


class EmbyInput:
    """
    Returns Emby Inputs

    Example:
        from_emby:
            server:
                host: http://localhost:8096
                username: <username>
                apikey: <apikey>
                return_host: wan
            list: TV
            types: series
    """

    auth = None

    schema = {
        'type': 'object',
        'properties': {
            **SCHEMA_SERVER_TAG,
            'list': {'type': 'string'},
            'types': one_or_more(
                {'type': 'string', 'enum': ['movie', 'series', 'season', 'episode']}
            ),
            'watched': {'type': 'boolean'},
            'favorite': {'type': 'boolean'},
            'sort': {
                'oneOf': [
                    {
                        'type': 'string',
                        'enum': SORT_FIELDS,
                    },
                    {
                        'type': 'object',
                        'properties': {
                            'field': {
                                'type': 'string',
                                'enum': SORT_FIELDS,
                            },
                            'order': {'type': 'string', 'enum': ['ascending', 'descending']},
                        },
                        'required': ['field', 'order'],
                    },
                ]
            },
        },
        'required': ['server'],
        'additionalProperties': False,
    }

    def login(self, config):
        if self.auth and self.auth.logged:
            return

        if not isinstance(config, dict):
            config = {}

        self.auth = EmbyAuth(**config)
        self.auth.login(True)

    def on_task_start(self, task, config):
        self.login(config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        self.login(config)

        s_lists = EmbyApi.search_list(**config)

        for s_list in s_lists:
            entry = s_list.to_entry()
            yield entry

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        self.login(config)

        s_list = EmbyApiList.get_api_list(**config)

        entries = []
        entries_obj = {}

        for search_string in entry.get('search_strings', [entry['title']]):
            entry['search_string'] = search_string
            media = s_list.get(entry)
            if not media:
                continue

            new_entry = media.to_entry()
            if 'emby_id' not in new_entry:
                continue

            entries_obj[new_entry['emby_id']] = new_entry

        for _, new_entry in entries_obj.items():
            entries.append(new_entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(EmbyInput, 'from_emby', interfaces=['search', 'task'], api_ver=2)
