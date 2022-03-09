from loguru import logger

from flexget import plugin
from flexget.components.jellyfin.api_jellyfin import JellyfinApi, JellyfinAuth
from flexget.components.jellyfin.jellyfin_util import SCHEMA_SERVER_TAG, SORT_FIELDS
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='from_jellyfin')


class JellyfinInput:
    """
    Returns Jellyfin Inputs

    Example:
        from_jellyfin:
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
        'required': ['server', 'list'],
        'additionalProperties': False,
    }

    def login(self, config):
        if self.auth and self.auth.logged:
            return

        if not isinstance(config, dict):
            config = {}

        self.auth = JellyfinAuth(**config)
        self.auth.login(True)

    def on_task_start(self, task, config):
        self.login(config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        self.login(config)

        s_lists = JellyfinApi.search_list(**config)

        for s_list in s_lists:
            entry = s_list.to_entry()
            yield entry


@event('plugin.register')
def register_plugin():
    plugin.register(JellyfinInput, 'from_jellyfin', api_ver=2)
