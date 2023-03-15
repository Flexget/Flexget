from loguru import logger

from flexget import entry, plugin
from flexget.event import event
from flexget.manager import Session

logger = logger.bind(name='tvmaze_lookup')


class PluginTVMazeLookup:
    """Retrieves tvmaze information for entries. Uses series_name,
    series_season, series_episode from series plugin.

    Example:

    tvmaze_lookup: yes

    Primarily used for passing tvmaze information to other plugins.

    This information is provided (via entry):

    series info:
    tvmaze_series_name
    tvmaze_series_year
    tvdb_id
    tvrage_id
    tvmaze_series_id
    tvmaze_series_show_id
    tvmaze_series_tvrage
    tvmaze_series_runtime
    tvmaze_series_premiered
    tvmaze_series_airdays
    tvmaze_series_weight
    tvmaze_series_update_date
    tvmaze_series_language
    tvmaze_series_original_image
    tvmaze_series_medium_image
    tvmaze_series_summary
    tvmaze_series_webchannel
    tvmaze_series_show_type
    tvmaze_genres
    tvmaze_series_network
    tvmaze_series_url
    tvmaze_series_status
    tvmaze_series_rating
    tvmaze_series_episodes

    episode info:
    tvmaze_episode_name
    tvmaze_season
    tvmaze_episode
    tvmaze_episode_id
    tvmaze_episode_airdate
    tvmaze_episode_url
    tvmaze_episode_original_image
    tvmaze_episode_medium_image
    tvmaze_episode_airstamp
    tvmaze_ep_overview
    tvmaze_ep_runtime

    """

    # Series info
    series_map = {
        'tvmaze_series_name': 'name',
        'tvmaze_series_year': 'year',
        'tvdb_id': 'tvdb_id',
        'tvrage_id': 'tvrage_id',
        'tvmaze_series_id': 'tvmaze_id',
        'tvmaze_series_show_id': 'tvmaze_id',
        'tvmaze_series_tvrage': 'tvrage_id',
        'tvmaze_series_runtime': 'runtime',
        'tvmaze_series_premiered': 'premiered',
        'tvmaze_series_airdays': 'schedule',
        'tvmaze_series_weight': 'weight',
        'tvmaze_series_update_date': 'updated',
        'tvmaze_series_language': 'language',
        'tvmaze_series_original_image': 'original_image',
        'tvmaze_series_medium_image': 'medium_image',
        'tvmaze_series_summary': 'summary',
        'tvmaze_series_webchannel': 'webchannel',
        'tvmaze_series_show_type': 'show_type',
        'tvmaze_genres': lambda i: [db_genre.name for db_genre in i.genres],
        'tvmaze_series_network': 'network',
        'tvmaze_series_url': 'url',
        'tvmaze_series_status': 'status',
        'tvmaze_series_rating': 'rating',
        'tvmaze_series_episodes': lambda show: [episodes.title for episodes in show.episodes],
    }

    # Season Info
    season_map = {
        'tvmaze_season_id': 'tvmaze_id',
        'tvmaze_season_series_id': 'series_id',
        'tvmaze_season_number': 'number',
        'tvmaze_season_url': 'url',
        'tvmaze_season_name': 'name',
        'tvmaze_season_episode_order': 'episode_order',
        'tvmaze_season_premiere_date': 'airdate',
        'tvmaze_season_end_date': 'end_date',
        'tvmaze_season_network': 'network',
        'tvmaze_season_web_channel': 'web_channel',
        'tvmaze_season_image': 'image',
        'tvmaze_season_summary': 'summary',
    }

    # Episode info
    episode_map = {
        'tvmaze_episode_name': 'title',
        'tvmaze_episode_season': 'season_number',
        'tvmaze_episode_number': 'number',
        'tvmaze_episode_id': 'tvmaze_id',
        'tvmaze_episode_airdate': 'airdate',
        'tvmaze_episode_url': 'url',
        'tvmaze_episode_summary': 'summary',
        'tvmaze_episode_original_image': 'original_image',
        'tvmaze_episode_medium_image': 'medium_image',
        'tvmaze_episode_airstamp': 'airstamp',
        'tvmaze_episode_runtime': 'runtime',
    }

    schema = {'type': 'boolean'}

    @entry.register_lazy_lookup('tvmaze_series_lookup')
    def lazy_series_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        series_lookup = plugin.get('api_tvmaze', self).series_lookup
        with Session() as session:
            lookupargs = {
                'title': entry.get('series_name', eval_lazy=False),
                'year': entry.get('year', eval_lazy=False),
                'tvmaze_id': entry.get('tvmaze_id', eval_lazy=False),
                'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                'tvrage_id': entry.get('tvrage_idk', eval_lazy=False),
                'session': session,
            }
            try:
                series = series_lookup(**lookupargs)
            except LookupError as e:
                logger.debug(e)
            else:
                entry.update_using_map(self.series_map, series)
        return entry

    @entry.register_lazy_lookup('tvmaze_season_lookup')
    def lazy_season_lookup(self, entry):
        season_lookup = plugin.get('api_tvmaze', self).season_lookup
        with Session(expire_on_commit=False) as session:
            lookupargs = {
                'title': entry.get('series_name', eval_lazy=False),
                'year': entry.get('year', eval_lazy=False),
                'tvmaze_id': entry.get('tvmaze_id', eval_lazy=False),
                'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                'tvrage_id': entry.get('tvrage_id', eval_lazy=False),
                'series_season': entry.get('series_season', eval_lazy=False),
                'session': session,
            }
            try:
                season = season_lookup(**lookupargs)
            except LookupError as e:
                logger.debug(e)
            else:
                entry.update_using_map(self.season_map, season)
        return entry

    @entry.register_lazy_lookup('tvmaze_episode_lookup')
    def lazy_episode_lookup(self, entry):
        episode_lookup = plugin.get('api_tvmaze', self).episode_lookup
        with Session(expire_on_commit=False) as session:
            lookupargs = {
                'title': entry.get('series_name', eval_lazy=False),
                'year': entry.get('year', eval_lazy=False),
                'tvmaze_id': entry.get('tvmaze_id', eval_lazy=False),
                'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                'tvrage_id': entry.get('tvrage_id', eval_lazy=False),
                'series_season': entry.get('series_season', eval_lazy=False),
                'series_episode': entry.get('series_episode', eval_lazy=False),
                'series_date': entry.get('series_date', eval_lazy=False),
                'series_id_type': entry.get('series_id_type', eval_lazy=False),
                'session': session,
            }
            try:
                episode = episode_lookup(**lookupargs)
            except LookupError as e:
                logger.debug(e)
            else:
                entry.update_using_map(self.episode_map, episode)
        return entry

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        for entry in task.entries:
            if (
                entry.get('series_name')
                or entry.get('tvdb_id', eval_lazy=False)
                or entry.get('tvmaze_id', eval_lazy=False)
                or entry.get('tvrage_id', eval_lazy=False)
            ):
                entry.add_lazy_fields(self.lazy_series_lookup, self.series_map)
                if entry.get('season_pack', eval_lazy=False):
                    entry.add_lazy_fields(self.lazy_season_lookup, self.season_map)
                if ('series_season' in entry and 'series_episode' in entry) or (
                    'series_date' in entry
                ):
                    entry.add_lazy_fields(self.lazy_episode_lookup, self.episode_map)

    @property
    def series_identifier(self):
        """Returns the plugin main identifier type"""
        return 'tvmaze_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        PluginTVMazeLookup, 'tvmaze_lookup', api_ver=2, interfaces=['task', 'series_metainfo']
    )
