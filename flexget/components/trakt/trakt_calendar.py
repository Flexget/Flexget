import datetime

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

from . import db

logger = logger.bind(name='trakt_calendar')

max_number_of_days = 31


class TraktCalendar:
    schema = {
        'type': 'object',
        'properties': {
            'start_day': {'type': 'integer', 'default': 0},
            'days': {'type': 'integer', 'default': 7},
            'account': {'type': 'string'},
            'strip_dates': {'type': 'boolean', 'default': False},
            'type': {'type': 'string', 'enum': ['shows', 'episodes']},
        },
        'required': ['type'],
        'additionalProperties': False,
    }

    # Series info
    series_map = {
        'trakt_series_name': 'title',
        'trakt_series_year': 'year',
        'imdb_id': 'ids.imdb',
        'tvdb_id': 'ids.tvdb',
        'tmdb_id': 'ids.tmdb',
        'trakt_show_id': 'ids.trakt',
        'trakt_slug': 'ids.slug',
        'tvrage_id': 'ids.tvrage',
        'trakt_trailer': 'trailer',
        'trakt_homepage': 'homepage',
        'trakt_series_runtime': 'runtime',
        'trakt_series_first_aired': 'first_aired',
        'trakt_series_air_time': 'airs.time',
        'trakt_series_air_day': 'airs.day',
        'trakt_series_air_timezone': 'airs.timezone',
        'trakt_series_content_rating': 'certification',
        'trakt_genres': 'genres',
        'trakt_series_network': 'network',
        'imdb_url': lambda s: s['ids']['imdb']
        and 'http://www.imdb.com/title/%s' % s['ids']['imdb'],
        'trakt_series_url': lambda s: s['ids']['slug']
        and 'https://trakt.tv/shows/%s' % s['ids']['slug'],
        'trakt_series_country': 'country',
        'trakt_series_status': 'status',
        'trakt_series_overview': 'overview',
        'trakt_series_rating': 'rating',
        'trakt_series_votes': 'votes',
        'trakt_series_language': 'language',
        'trakt_series_aired_episodes': 'aired_episodes',
        'trakt_languages': 'available_translations',
        'trakt_series_updated_at': 'updated_at',
    }

    # Episode info
    episode_map = {
        'trakt_ep_name': 'title',
        'trakt_ep_imdb_id': 'ids.imdb',
        'trakt_ep_tvdb_id': 'ids.tvdb',
        'trakt_ep_tmdb_id': 'ids.tmdb',
        'trakt_ep_tvrage': 'ids.tvrage',
        'trakt_episode_id': 'ids.trakt',
        'trakt_ep_first_aired': 'first_aired',
        'trakt_ep_overview': 'overview',
        'trakt_ep_abs_number': 'number_abs',
        'trakt_season': 'season',
        'trakt_episode': 'number',
        'trakt_ep_id': lambda ep: 'S%02dE%02d' % (ep['season'], ep['number']),
        'trakt_ep_languages': 'available_translations',
        'trakt_ep_runtime': 'runtime',
        'trakt_ep_updated_at': 'updated_at',
        'trakt_ep_rating': 'rating',
        'trakt_ep_votes': 'votes',
    }

    @cached('trakt_calendar', persist='2 hours')
    def on_task_input(self, task, config):
        start_date = datetime.datetime.now().date() + datetime.timedelta(days=config['start_day'])
        entries = set()

        # The API limit is max_number_of_days days for a single call.
        for start_day in range(0, config['days'], max_number_of_days):
            current_start_date = start_date + datetime.timedelta(days=start_day)
            number_of_days = min(config['days'] - start_day, max_number_of_days)

            logger.debug(
                'Start date for calendar: {}, end date: {}',
                current_start_date,
                current_start_date + datetime.timedelta(days=number_of_days),
            )

            url = db.get_api_url(
                'calendars',
                'my' if config.get('account') else 'all',
                'shows',
                current_start_date,
                number_of_days,
            )

            try:
                results = (
                    db.get_session(config.get('account'))
                    .get(url, params={'extended': 'full'})
                    .json()
                )
                logger.debug('Found {} calendar entries', len(results))
            except RequestException as e:
                raise plugin.PluginError(f'Error while fetching calendar: {e}')

            for result in results:
                e = Entry()
                e.update_using_map(self.series_map, result['show'])
                if config['type'] == 'episodes':
                    e.update_using_map(self.episode_map, result['episode'])

                title = e['trakt_series_name']
                if not config['strip_dates']:
                    title = '{} ({})'.format(title, e['trakt_series_year'])

                url = e['trakt_series_url']

                if config['type'] == 'episodes':
                    title = '{} S{:02d}E{:02d}'.format(
                        title, e['trakt_season'], e['trakt_episode']
                    )

                    url = '{}/seasons/{}/episodes/{}'.format(
                        url, e['trakt_season'], e['trakt_episode']
                    )

                e['title'] = title
                e['url'] = url

                entries.add(e)

        return list(entries)


@event('plugin.register')
def register_plugin():
    plugin.register(TraktCalendar, 'trakt_calendar', api_ver=2, interfaces=['task'])
