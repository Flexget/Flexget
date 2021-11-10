from loguru import logger

from flexget import plugin
from flexget.components.emby.api_emby import EmbyApiLibrary, EmbyAuth
from flexget.components.emby.emby_util import SCHEMA_SERVER_TAG
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='emby_reload')


class EmbyRefreshLibrary:
    """
    Refresh Emby Library

    Example:
        emby_refresh:
            server:
                host: http://localhost:8096
                username: <username>
                apikey: <apikey>
                return_host: wan
            when: accepted
    """

    auth = None

    schema = {
        'type': 'object',
        'properties': {
            **SCHEMA_SERVER_TAG,
            'when': one_or_more(
                {
                    'type': 'string',
                    'enum': ['accepted', 'rejected', 'failed', 'no_entries', 'aborted', 'always'],
                }
            ),
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

    def prepare_config(self, config):
        config.setdefault('when', ['always'])

        when = config['when']
        if when and not isinstance(when, list):
            config['when'] = [when]

        return

    def library_refresh(self):
        EmbyApiLibrary.library_refresh(self.auth)

    def on_task_start(self, task, config):
        self.login(config)

    @plugin.internet(logger)
    def on_task_exit(self, task, config):
        self.login(config)
        self.prepare_config(config)

        conditions = [
            task.accepted and 'accepted' in config['when'],
            task.rejected and 'rejected' in config['when'],
            task.failed and 'failed' in config['when'],
            not task.all_entries and 'no_entries' in config['when'],
            'always' in config['when'],
        ]

        if any(conditions):
            self.library_refresh()

    def on_task_abort(self, task, config):
        self.prepare_config(config)

        if 'aborted' in config['when']:
            self.library_refresh()


@event('plugin.register')
def register_plugin():
    plugin.register(EmbyRefreshLibrary, 'emby_refresh', api_ver=2)
