from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import split_title_year

logger = logger.bind(name='est_series_tvmaze')


class EstimatesSeriesTVMaze:
    @plugin.priority(2)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season']):
            return
        series_name = entry['series_name']
        season = entry['series_season']
        episode_number = entry.get('series_episode')
        title, year_match = split_title_year(series_name)

        # This value should be added to input plugins to trigger a season lookuo
        season_pack = entry.get('season_pack_lookup')

        kwargs = {
            'tvmaze_id': entry.get('tvmaze_id'),
            'tvdb_id': entry.get('tvdb_id') or entry.get('trakt_series_tvdb_id'),
            'tvrage_id': entry.get('tvrage_id') or entry.get('trakt_series_tvrage_id'),
            'imdb_id': entry.get('imdb_id'),
            'show_name': title,
            'show_year': entry.get('trakt_series_year')
            or entry.get('year')
            or entry.get('imdb_year')
            or year_match,
            'show_network': entry.get('network') or entry.get('trakt_series_network'),
            'show_country': entry.get('country') or entry.get('trakt_series_country'),
            'show_language': entry.get('language'),
            'series_season': season,
            'series_episode': episode_number,
            'series_name': series_name,
        }

        api_tvmaze = plugin.get('api_tvmaze', self)
        if season_pack:
            lookup = api_tvmaze.season_lookup
            logger.debug('Searching api_tvmaze for season')
        else:
            logger.debug('Searching api_tvmaze for episode')
            lookup = api_tvmaze.episode_lookup

        for k, v in list(kwargs.items()):
            if v:
                logger.debug('{}: {}', k, v)

        entity_data = {'data_exists': True, 'entity_date': None}
        entity = {}
        try:
            entity = lookup(**kwargs)
        except LookupError as e:
            logger.debug(str(e))
            entity_data['data_exists'] = False
        if entity and entity.airdate:
            logger.debug('received air-date: {}', entity.airdate)
            entity_data['entity_date'] = entity.airdate

        if entity_data['data_exists'] == False:
            # Make Lookup to series to see if failed because of no episode or no data
            lookup = api_tvmaze.series_lookup
            series = {}
            try:
                series = lookup(**kwargs)
            except LookupError:
                entity_data['data_exists'] = False

            if not series:
                logger.debug('No data in tvmaze for series: {}', series_name)
                entity_data['data_exists'] = False
            else:
                logger.debug(
                    'No information to episode, but series {} exists in tvmaze', series_name
                )
                entity_data['data_exists'] = True

        return entity_data


@event('plugin.register')
def register_plugin():
    plugin.register(
        EstimatesSeriesTVMaze, 'est_series_tvmaze', interfaces=['estimate_release'], api_ver=2
    )
