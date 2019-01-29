# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import, print_function

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.manager import Session

from . import api_trakt as plugin_api_trakt
from . import db

# TODO: not very nice ..
lookup_series = plugin_api_trakt.ApiTrakt.lookup_series
lookup_movie = plugin_api_trakt.ApiTrakt.lookup_movie


log = logging.getLogger('trakt_lookup')


def is_show(entry):
    return entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False)


def is_episode(entry):
    return entry.get('series_season') and entry.get('series_episode')


def is_season(entry):
    return entry.get('series_season') and not is_episode(entry)


def is_movie(entry):
    return bool(entry.get('movie_name'))


class TraktLazyLookup(object):
    def __init__(self, field_map, lookup_function):
        self.field_map = field_map
        self.lookup_function = lookup_function

    def __call__(self, entry):
        with Session() as session:
            try:
                result = self.lookup_function(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.field_map, result)

        return entry


class TraktUserDataLookup(object):
    def __init__(self, field_name, data_type, media_type, lookup_function):
        self.field_name = field_name
        self.lookup_function = lookup_function
        self.data_type = data_type
        self.media_type = media_type

    def __call__(self, entry):
        try:
            result = self.lookup_function(
                data_type=self.data_type, media_type=self.media_type, entry=entry
            )
        except LookupError as e:
            log.debug(e)
        else:
            entry[self.field_name] = result

        return entry


class PluginTraktLookup(object):
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

    # Series info
    series_map = {
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
    }

    series_actor_map = {'trakt_actors': lambda show: db.list_actors(show.actors)}
    show_translate_map = {
        'trakt_translations': lambda show: db.get_translations_dict(show.translations, 'show')
    }

    # Episode info
    episode_map = {
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
    }

    # Season info
    season_map = {
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
    }

    # Movie info
    movie_map = {
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
    }

    movie_translate_map = {
        'trakt_translations': lambda movie: db.get_translations_dict(movie.translations, 'movie')
    }

    movie_actor_map = {'trakt_actors': lambda movie: db.list_actors(movie.actors)}

    user_data_map = {
        'collected': 'trakt_collected',
        'watched': 'trakt_watched',
        'ratings': {
            'show': 'trakt_series_user_rating',
            'season': 'trakt_season_user_rating',
            'episode': 'trakt_ep_user_rating',
            'movie': 'trakt_movie_user_rating',
        },
    }

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

    def __init__(self):
        self.getter_map = {
            'show': self._get_series,
            'season': self._get_season,
            'episode': self._get_episode,
            'movie': self._get_movie,
        }

    def on_task_start(self, task, config):
        if not isinstance(config, dict):
            config = {}

        self.trakt = plugin_api_trakt.ApiTrakt(
            username=config.get('username'), account=config.get('account')
        )

    def _get_user_data_field_name(self, data_type, media_type):
        if data_type not in self.user_data_map:
            raise plugin.PluginError('Unknown user data type "%s"' % data_type)

        if isinstance(self.user_data_map[data_type], dict):
            return self.user_data_map[data_type][media_type]

        return self.user_data_map[data_type]

    def _get_lookup_args(self, entry):
        args = {
            'title': entry.get('series_name', eval_lazy=False)
            or entry.get('title', eval_lazy=False),
            'year': entry.get('year', eval_lazy=False),
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

    def _get_series(self, entry, session):
        series_lookup_args = self._get_lookup_args(entry)
        return lookup_series(session=session, **series_lookup_args)

    def _get_season(self, entry, session):
        series_lookup_args = self._get_lookup_args(entry)
        show = lookup_series(session=session, **series_lookup_args)
        return show.get_season(entry['series_season'], session)

    def _get_episode(self, entry, session):
        series_lookup_args = self._get_lookup_args(entry)
        show = lookup_series(session=session, **series_lookup_args)
        return show.get_episode(entry['series_season'], entry['series_episode'], session)

    def _get_movie(self, entry, session):
        movie_lookup_args = self._get_lookup_args(entry)
        return lookup_movie(session=session, **movie_lookup_args)

    def lazy_lookup(self, entry, media_type, mapping):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                trakt_media = self.getter_map[media_type](entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(mapping, trakt_media)
        return entry

    def _lazy_user_data_lookup(self, data_type, media_type, entry):
        try:
            lookup = self.getter_map[media_type]
            user_data_lookup = self.trakt.lookup_map[data_type][media_type]
        except KeyError:
            raise plugin.PluginError(
                'Unknown data type="%s" or media type="%s"' % (data_type, media_type)
            )

        with Session() as session:
            try:
                return user_data_lookup(lookup(entry, session), entry['title'])
            except LookupError as e:
                log.debug(e)

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        if isinstance(config, bool):
            config = dict()

        for entry in task.entries:
            if is_show(entry):
                entry.register_lazy_func(
                    TraktLazyLookup(self.series_map, self._get_series), self.series_map
                )
                # TODO cleaner way to do this?
                entry.register_lazy_func(
                    TraktLazyLookup(self.series_actor_map, self._get_series), self.series_actor_map
                )
                entry.register_lazy_func(
                    TraktLazyLookup(self.show_translate_map, self._get_series),
                    self.show_translate_map,
                )
                if is_episode(entry):
                    entry.register_lazy_func(
                        TraktLazyLookup(self.episode_map, self._get_episode), self.episode_map
                    )
                elif is_season(entry):
                    entry.register_lazy_func(
                        TraktLazyLookup(self.season_map, self._get_season), self.season_map
                    )
            else:
                entry.register_lazy_func(
                    TraktLazyLookup(self.movie_map, self._get_movie), self.movie_map
                )
                # TODO cleaner way to do this?
                entry.register_lazy_func(
                    TraktLazyLookup(self.movie_actor_map, self._get_movie), self.movie_actor_map
                )
                entry.register_lazy_func(
                    TraktLazyLookup(self.movie_translate_map, self._get_movie),
                    self.movie_translate_map,
                )

            if config.get('username') or config.get('account'):
                self._register_lazy_user_data_lookup(entry, 'collected')
                self._register_lazy_user_data_lookup(entry, 'watched')
                self._register_lazy_user_ratings_lookup(entry)

    def _get_media_type_from_entry(self, entry):
        media_type = None
        if is_episode(entry):
            media_type = 'episode'
        elif is_season(entry):
            media_type = 'season'
        elif is_show(entry):
            media_type = 'show'
        elif is_movie(entry):
            media_type = 'movie'

        return media_type

    def _register_lazy_user_data_lookup(self, entry, data_type, media_type=None):
        media_type = media_type or self._get_media_type_from_entry(entry)
        if not media_type:
            return
        field_name = self._get_user_data_field_name(data_type=data_type, media_type=media_type)
        entry.register_lazy_func(
            TraktUserDataLookup(field_name, data_type, media_type, self._lazy_user_data_lookup),
            [field_name],
        )

    def _register_lazy_user_ratings_lookup(self, entry):
        data_type = 'ratings'

        if is_show(entry):
            self._register_lazy_user_data_lookup(
                entry=entry, data_type=data_type, media_type='show'
            )
            self._register_lazy_user_data_lookup(
                entry=entry, data_type=data_type, media_type='season'
            )
            self._register_lazy_user_data_lookup(
                entry=entry, data_type=data_type, media_type='episode'
            )
        else:
            self._register_lazy_user_data_lookup(
                entry=entry, data_type=data_type, media_type='movie'
            )

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
