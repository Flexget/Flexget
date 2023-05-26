from typing import Optional

from loguru import logger

from flexget import plugin
from flexget.entry import Entry, register_lazy_lookup
from flexget.event import event
from flexget.manager import Session

from . import api_trakt as plugin_api_trakt
from . import db

# TODO: not very nice ..
lookup_series = plugin_api_trakt.ApiTrakt.lookup_series
lookup_movie = plugin_api_trakt.ApiTrakt.lookup_movie


logger = logger.bind(name='trakt_lookup')


def is_show(entry: Entry) -> bool:
    return entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False)


def is_episode(entry: Entry) -> bool:
    return entry.get('series_season') and entry.get('series_episode')


def is_season(entry: Entry) -> bool:
    return entry.get('series_season') and not is_episode(entry)


def is_movie(entry: Entry) -> bool:
    return bool(entry.get('movie_name'))


def get_media_type_for_entry(entry: Entry) -> Optional[str]:
    if is_episode(entry):
        return 'episode'
    elif is_season(entry):
        return 'season'
    elif is_show(entry):
        return 'show'
    elif is_movie(entry):
        return 'movie'
    return None


@register_lazy_lookup('trakt_user_data_lookup')
def trakt_user_data_lookup(entry, field_name, data_type, media_type, username, account):
    trakt = plugin_api_trakt.ApiTrakt(username=username, account=account)
    user_data_lookup = trakt.lookup_map[data_type][media_type]

    try:
        with Session() as session:
            result = user_data_lookup(get_db_data_for(media_type, entry, session), entry['title'])
    except LookupError as e:
        logger.debug(e)
    else:
        entry[field_name] = result

    return entry


def _get_lookup_args(entry: Entry) -> dict:
    args = {
        'title': entry.get('series_name', eval_lazy=False) or entry.get('title', eval_lazy=False),
        'year': entry.get('year', eval_lazy=False) or entry.get('movie_year', eval_lazy=False),
        'trakt_slug': (
            entry.get('trakt_show_slug', eval_lazy=False)
            or entry.get('trakt_movie_slug', eval_lazy=False)
        ),
        'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
        'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
        'imdb_id': entry.get('imdb_id', eval_lazy=False),
        'tvrage_id': entry.get('tvrage_id', eval_lazy=False),
    }

    if entry.get('trakt_movie_id', eval_lazy=False):
        args['trakt_id'] = entry['trakt_movie_id']
    elif entry.get('trakt_show_id', eval_lazy=False):
        args['trakt_id'] = entry['trakt_show_id']
    elif is_movie(entry) and entry.get('trakt_movie_id', eval_lazy=True):
        args['trakt_id'] = entry['trakt_movie_id']
    elif entry.get('trakt_show_id', eval_lazy=True):
        args['trakt_id'] = entry['trakt_show_id']

    return args


def get_db_data_for(data_type: str, entry: Entry, session: Session):
    if data_type == 'movie':
        movie_lookup_args = _get_lookup_args(entry)
        return lookup_movie(session=session, **movie_lookup_args)
    series_lookup_args = _get_lookup_args(entry)
    show = lookup_series(session=session, **series_lookup_args)
    if data_type == 'show':
        return show
    if data_type == 'season':
        return show.get_season(entry['series_season'], session)
    if data_type == 'episode':
        return show.get_episode(entry['series_season'], entry['series_episode'], session)


lazy_lookup_types = {
    'show': {
        'trakt_series_name': 'title',
        'trakt_series_year': 'year',
        'imdb_id': 'imdb_id',
        'tvdb_id': 'tvdb_id',
        'tmdb_id': 'tmdb_id',
        'trakt_show_id': 'id',
        'trakt_show_slug': 'slug',
        'tvrage_id': 'tvrage_id',
        'trakt_trailer': 'trailer',
        'trakt_homepage': 'homepage',
        'trakt_series_runtime': 'runtime',
        'trakt_series_first_aired': 'first_aired',
        'trakt_series_air_time': 'air_time',
        'trakt_series_air_day': 'air_day',
        'trakt_series_content_rating': 'certification',
        'trakt_genres': lambda i: [db_genre.name for db_genre in i.genres],
        'trakt_series_network': 'network',
        'imdb_url': lambda series: series.imdb_id
        and 'http://www.imdb.com/title/%s' % series.imdb_id,
        'trakt_series_url': lambda series: series.slug
        and 'https://trakt.tv/shows/%s' % series.slug,
        'trakt_series_country': 'country',
        'trakt_series_status': 'status',
        'trakt_series_overview': 'overview',
        'trakt_series_rating': 'rating',
        'trakt_series_votes': 'votes',
        'trakt_series_language': 'language',
        'trakt_series_aired_episodes': 'aired_episodes',
        'trakt_series_episodes': lambda show: [episodes.title for episodes in show.episodes],
        'trakt_languages': 'translation_languages',
    },
    'show_actors': {'trakt_actors': lambda show: db.list_actors(show.actors)},
    'show_translations': {
        'trakt_translations': lambda show: db.get_translations_dict(show.translations, 'show')
    },
    'season': {
        'trakt_season_name': 'title',
        'trakt_season_tvdb_id': 'tvdb_id',
        'trakt_season_tmdb_id': 'tmdb_id',
        'trakt_season_tvrage': 'tvrage_id',
        'trakt_season_id': 'id',
        'trakt_season_first_aired': 'first_aired',
        'trakt_season_overview': 'overview',
        'trakt_season_episode_count': 'episode_count',
        'trakt_season': 'number',
        'trakt_season_aired_episodes': 'aired_episodes',
    },
    'episode': {
        'trakt_ep_name': 'title',
        'trakt_ep_imdb_id': 'imdb_id',
        'trakt_ep_tvdb_id': 'tvdb_id',
        'trakt_ep_tmdb_id': 'tmdb_id',
        'trakt_ep_tvrage': 'tvrage_id',
        'trakt_episode_id': 'id',
        'trakt_ep_first_aired': 'first_aired',
        'trakt_ep_overview': 'overview',
        'trakt_ep_abs_number': 'number_abs',
        'trakt_season': 'season',
        'trakt_episode': 'number',
        'trakt_ep_id': lambda ep: 'S%02dE%02d' % (ep.season, ep.number),
    },
    'movie': {
        'movie_name': 'title',
        'movie_year': 'year',
        'trakt_movie_name': 'title',
        'trakt_movie_year': 'year',
        'trakt_movie_id': 'id',
        'trakt_movie_slug': 'slug',
        'imdb_id': 'imdb_id',
        'tmdb_id': 'tmdb_id',
        'trakt_tagline': 'tagline',
        'trakt_overview': 'overview',
        'trakt_released': 'released',
        'trakt_runtime': 'runtime',
        'trakt_rating': 'rating',
        'trakt_votes': 'votes',
        'trakt_homepage': 'homepage',
        'trakt_trailer': 'trailer',
        'trakt_language': 'language',
        'trakt_genres': lambda i: [db_genre.name for db_genre in i.genres],
        'trakt_languages': 'translation_languages',
    },
    'movie_actors': {'trakt_actors': lambda movie: db.list_actors(movie.actors)},
    'movie_translations': {
        'trakt_translations': lambda movie: db.get_translations_dict(movie.translations, 'movie')
    },
}


@register_lazy_lookup('trakt_lazy_lookup')
def lazy_lookup(entry, lazy_lookup_name, media_type):
    with Session() as session:
        try:
            db_data = get_db_data_for(media_type, entry, session)
        except LookupError as e:
            logger.debug(e)
        else:
            entry.update_using_map(lazy_lookup_types[lazy_lookup_name], db_data)
    return entry


def add_lazy_fields(entry: Entry, lazy_lookup_name: str, media_type: str) -> None:
    """
    Adds lazy fields for one of the lookups in our `lazy_lookup_types` dict.

    :param entry: The entry to add lazy fields to.
    :param lazy_lookup_name: One of the keys in `lazy_lookup_types` dict.
    :param media_type: show/season/episode/movie (the type of db data needed for this lazy lookup)
    """
    entry.add_lazy_fields(
        lazy_lookup, lazy_lookup_types[lazy_lookup_name], args=(lazy_lookup_name, media_type)
    )


user_data_fields = {
    'collected': 'trakt_collected',
    'watched': 'trakt_watched',
    'ratings': {
        'show': 'trakt_series_user_rating',
        'season': 'trakt_season_user_rating',
        'episode': 'trakt_ep_user_rating',
        'movie': 'trakt_movie_user_rating',
    },
}


def add_lazy_user_fields(
    entry: Entry, data_type: str, media_type: str, username: str, account: str
) -> None:
    """
    Adds one of the user field lazy lookups to an entry.

    :param entry: Entry to add lazy fields to
    :param data_type: ratings/collected/watched (one of the keys in `user_data_fields` dict.)
    :param media_type: show/season/episode/movie
    :param username: Either this or account is required, the other can be None
    :param account: Either this or username is required, the other can be None
    """
    field_name = user_data_fields[data_type]
    if data_type == 'ratings':
        field_name = field_name[media_type]
    entry.add_lazy_fields(
        trakt_user_data_lookup,
        [field_name],
        args=(field_name, data_type, media_type, username, account),
    )


class PluginTraktLookup:
    """Retrieves trakt information for entries. Uses series_name,
    series_season, series_episode from series plugin.

    Example:

    trakt_lookup: yes

    Primarily used for passing trakt information to other plugins.
    Among these is the IMDB url for the series.

    This information is provided (via entry):
    series info:
    trakt_series_name
    trakt_series_runtime
    trakt_series_first_aired_epoch
    trakt_series_first_aired_iso
    trakt_series_air_time
    trakt_series_content_ratingi
    trakt_series_genres
    trakt_series_imdb_url
    trakt_series_trakt_url
    imdb_id
    tvdb_id
    trakt_series_actors
    trakt_series_country
    trakt_series_year
    trakt_series_tvrage_id
    trakt_series_status
    trakt_series_overview

    trakt_ep_name
    trakt_ep_season
    trakt_ep_number
    trakt_ep_overview
    trakt_ep_first_aired_epoch
    trakt_ep_first_aired_iso
    trakt_ep_id
    trakt_ep_tvdb_id


    """

    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {'account': {'type': 'string'}, 'username': {'type': 'string'}},
                'anyOf': [{'required': ['username']}, {'required': ['account']}],
                'error_anyOf': 'At least one of `username` or `account` options are needed.',
                'additionalProperties': False,
            },
            {'type': 'boolean'},
        ]
    }

    def on_task_start(self, task, config):
        if not isinstance(config, dict):
            config = {}

        self.trakt = plugin_api_trakt.ApiTrakt(
            username=config.get('username'), account=config.get('account')
        )

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        if isinstance(config, bool):
            config = {}

        for entry in task.entries:
            if is_show(entry):
                add_lazy_fields(entry, 'show', media_type='show')
                add_lazy_fields(entry, 'show_actors', media_type='show')
                add_lazy_fields(entry, 'show_translations', media_type='show')
                if is_episode(entry):
                    add_lazy_fields(entry, 'episode', media_type='episode')
                elif is_season(entry):
                    add_lazy_fields(entry, 'season', media_type='season')
            else:
                add_lazy_fields(entry, 'movie', media_type='movie')
                add_lazy_fields(entry, 'movie_actors', media_type='movie')
                add_lazy_fields(entry, 'movie_translations', media_type='movie')

            if config.get('username') or config.get('account'):
                credentials = {
                    'username': config.get('username'),
                    'account': config.get('account'),
                }
                media_type = get_media_type_for_entry(entry)
                if media_type:
                    add_lazy_user_fields(entry, 'collected', media_type=media_type, **credentials)
                    add_lazy_user_fields(entry, 'watched', media_type=media_type, **credentials)
                if is_show(entry):
                    add_lazy_user_fields(entry, 'ratings', media_type='show', **credentials)
                    if is_season(entry):
                        add_lazy_user_fields(entry, 'ratings', media_type='season', **credentials)
                    if is_episode(entry):
                        add_lazy_user_fields(entry, 'ratings', media_type='episode', **credentials)
                elif is_movie(entry):
                    add_lazy_user_fields(entry, 'ratings', media_type='movie', **credentials)

    @property
    def series_identifier(self):
        """Returns the plugin main identifier type"""
        return 'trakt_show_id'

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'trakt_movie_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        PluginTraktLookup,
        'trakt_lookup',
        api_ver=2,
        interfaces=['task', 'series_metainfo', 'movie_metainfo'],
    )
