from loguru import logger

from flexget import entry, plugin
from flexget.components.emby.api_emby import EmbyApi, EmbyAuth
from flexget.components.emby.emby_util import SCHEMA_SERVER, get_field_map
from flexget.event import event

logger = logger.bind(name='emby_lookup')


class EmbyLookup:
    """
    Preforms Emby Lookup

    Example:
        emby_lookup:
            host: http://localhost:8096
            username: <username>
            apikey: <apikey>
            return_host: wan
    """

    auth = {}

    schema = {**SCHEMA_SERVER}

    def on_task_start(self, task, config):
        if not isinstance(config, dict):
            config = {}

        self.auth = EmbyAuth(**config)

        try:
            self.auth.login(False)
        except plugin.PluginError as e:
            logger.error('Not possible to login to emby: {}', e)

    @entry.register_lazy_lookup('emby_lookup')
    def lazy_loader(self, entry, auth):
        if not auth:
            return

        if not auth.logged:
            auth.login()

        emby_api = EmbyApi(auth)
        emby_data = emby_api.search(**entry)

        if not emby_data:
            return

        emby_type = EmbyApi.get_type(**emby_data)

        lazy_fields = get_field_map(media_type=emby_type)
        if not lazy_fields:
            return

        entry.update_using_map(lazy_fields, emby_data, ignore_none=True)

    def add_lazy(self, entry, media_type):
        lazy_fields = get_field_map(media_type=media_type)

        entry.add_lazy_fields(self.lazy_loader, lazy_fields, kwargs={'auth': self.auth})

        entry['emby_server_id'] = self.auth.server_id
        entry['emby_username'] = self.auth.username
        entry['emby_user_id'] = self.auth.uid

    # Run after series and metainfo series and imdb
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        for entry in task.entries:
            self.add_lazy(entry, EmbyApi.get_type(**entry))

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'emby_movie_id'

    @property
    def series_identifier(self):
        """Returns the plugin main identifier type"""
        return 'emby_serie_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        EmbyLookup,
        'emby_lookup',
        api_ver=2,
        interfaces=['task', 'series_metainfo', 'movie_metainfo'],
    )
