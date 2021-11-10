from loguru import logger

from flexget import plugin
from flexget.components.emby.api_emby import EmbyApi, EmbyApiList, EmbyAuth
from flexget.components.emby.emby_util import SCHEMA_SERVER_TAG
from flexget.event import event

logger = logger.bind(name='emby_list')


class PluginEmbyList:
    """
    Returns Emby Lists

    Example:
        emby_list:
            server:
                host: http://localhost:8096
                username: <username>
                apikey: <apikey>
                return_host: wan
            list: watched
    """

    auth = None

    schema = {
        'type': 'object',
        'properties': {
            **SCHEMA_SERVER_TAG,
            'list': {'type': 'string'},
        },
        'required': ['server', 'list'],
        'additionalProperties': False,
    }

    def login(self, config):
        if self.auth and self.auth.logged:
            return

        if not isinstance(config, dict):
            config = {}

        self.auth = EmbyAuth(**config)
        self.auth.login(True)

    def get_list(self, config):
        self.login(config)
        return EmbyApiList(auth=self.auth, **config)

    def on_task_start(self, task, config):
        self.login(config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        self.login(config)

        s_lists = EmbyApi.search_list(auth=self.auth, **config)

        for s_list in s_lists:
            entry = s_list.to_entry()
            yield entry


@event('plugin.register')
def register_plugin():
    plugin.register(PluginEmbyList, 'emby_list', api_ver=2, interfaces=['task', 'list'])
