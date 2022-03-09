from loguru import logger

from flexget import entry, plugin
from flexget.components.jellyfin.api_jellyfin import JellyfinApi, JellyfinAuth
from flexget.components.jellyfin.jellyfin_util import SCHEMA_SERVER, get_field_map
from flexget.event import event

logger = logger.bind(name='jellyfin_lookup')


class JellyfinLookup:
    """
    Preforms Jellyfin Lookup

    Example:
        jellyfin_lookup:
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

        self.auth = JellyfinAuth(**config)
        self.auth.login(False)

    @entry.register_lazy_lookup('jellyfin_lookup')
    def lazy_loader(self, entry, auth):
        if not auth:
            return

        if not auth.logged:
            auth.login()

        jellyfin_api = JellyfinApi(auth)
        jellyfin_data = jellyfin_api.search(**entry)

        if not jellyfin_data:
            return

        jellyfin_type = JellyfinApi.get_type(**jellyfin_data)

        lazy_fields = get_field_map(media_type=jellyfin_type)
        if not lazy_fields:
            return

        entry.update_using_map(lazy_fields, jellyfin_data, ignore_none=True)

    def add_lazy(self, entry, media_type):
        lazy_fields = get_field_map(media_type=media_type)

        entry.add_lazy_fields(self.lazy_loader, lazy_fields, kwargs={'auth': self.auth})

        entry['jellyfin_server_id'] = self.auth.server_id
        entry['jellyfin_username'] = self.auth.username
        entry['jellyfin_user_id'] = self.auth.uid

    # Run after series and metainfo series and imdb
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        for entry in task.entries:
            self.add_lazy(entry, JellyfinApi.get_type(**entry))

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'jellyfin_movie_id'

    @property
    def series_identifier(self):
        """Returns the plugin main identifier type"""
        return 'jellyfin_serie_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        JellyfinLookup,
        'jellyfin_lookup',
        api_ver=2,
        interfaces=['task', 'series_metainfo', 'movie_metainfo'],
    )
