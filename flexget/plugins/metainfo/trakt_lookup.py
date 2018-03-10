# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.manager import Session

try:
    from flexget.plugins.internal.api_trakt import ApiTrakt, list_actors, get_translations_dict

    lookup_series = ApiTrakt.lookup_series
    lookup_movie = ApiTrakt.lookup_movie
except ImportError:
    raise plugin.DependencyError(issued_by='trakt_lookup', missing='api_trakt',
                                 message='trakt_lookup requires the `api_trakt` plugin')

log = logging.getLogger('trakt_lookup')


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
    trakt_series_content_rating
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
        'trakt_slug': 'slug',
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
        'imdb_url': lambda series: series.imdb_id and 'http://www.imdb.com/title/%s' % series.imdb_id,
        'trakt_series_url': lambda series: series.slug and 'https://trakt.tv/shows/%s' % series.slug,
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

    series_actor_map = {
        'trakt_actors': lambda show: list_actors(show.actors),
    }
    show_translate_map = {
        'trakt_translations': lambda show: get_translations_dict(show.translations, 'show'),
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
        'trakt_slug': 'slug',
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
        'trakt_translations': lambda movie: get_translations_dict(movie.translations, 'movie'),
    }

    movie_actor_map = {
        'trakt_actors': lambda movie: list_actors(movie.actors),
    }

    schema = {'oneOf': [
        {
            'type': 'object',
            'properties': {
                'account': {'type': 'string'},
                'username': {'type': 'string'},
            },
            'anyOf': [{'required': ['username']}, {'required': ['account']}],
            'error_anyOf': 'At least one of `username` or `account` options are needed.',
            'additionalProperties': False

        },
        {
            'type': 'boolean'
        }
    ]}

    def on_task_start(self, task, config):
        if isinstance(config, dict):
            self.trakt = ApiTrakt(username=config.get('username'), account=config.get('account'))
        else:
            self.trakt = ApiTrakt()

    def __get_series_lookup_args(self, entry):
        return {
            'title': entry.get('series_name', eval_lazy=False),
            'year': entry.get('year', eval_lazy=False),
            'trakt_id': entry.get('trakt_show_id', eval_lazy=True),
            'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
            'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
        }

    def __get_movie_lookup_args(self, entry):
        return {
            'title': entry.get('title', eval_lazy=False),
            'year': entry.get('year', eval_lazy=False),
            'trakt_id': entry.get('trakt_movie_id', eval_lazy=True),
            'trakt_slug': entry.get('trakt_movie_slug', eval_lazy=False),
            'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
            'imdb_id': entry.get('imdb_id', eval_lazy=False),
        }

    def __get_series(self, entry, session):
        series_lookup_args = self.__get_series_lookup_args(entry)
        return lookup_series(session=session, **series_lookup_args)

    def __get_season(self, entry, session):
        series_lookup_args = self.__get_series_lookup_args(entry)
        show = lookup_series(session=session, **series_lookup_args)
        return show.get_season(entry['series_season'], session)

    def __get_episode(self, entry, session):
        series_lookup_args = self.__get_series_lookup_args(entry)
        show = lookup_series(session=session, **series_lookup_args)
        return show.get_episode(entry['series_season'], entry['series_episode'], session)

    def __get_movie(self, entry, session):
        movie_lookup_args = self.__get_movie_lookup_args(entry)
        return lookup_movie(session=session, **movie_lookup_args)

    def lazy_series_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                series = self.__get_series(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.series_map, series)
        return entry

    def lazy_series_actor_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                series = self.__get_series(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.series_actor_map, series)
        return entry

    def lazy_series_translate_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                series = self.__get_series(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.show_translate_map, series)
        return entry

    def lazy_episode_lookup(self, entry):
        with Session() as session:
            try:
                episode = self.__get_episode(entry, session)
            except LookupError as e:
                log.debug('Error looking up trakt episode information for %s: %s', entry['title'], e)
            else:
                entry.update_using_map(self.episode_map, episode)
        return entry

    def lazy_season_lookup(self, entry):
        with Session() as session:
            try:
                season = self.__get_season(entry, session)
            except LookupError as e:
                log.debug('Error looking up trakt season information for %s: %s', entry['title'], e)
            else:
                entry.update_using_map(self.season_map, season)
        return entry

    def lazy_movie_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                movie = self.__get_movie(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.movie_map, movie)
        return entry

    def lazy_movie_actor_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                movie = self.__get_movie(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.movie_actor_map, movie)
        return entry

    def lazy_movie_translate_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            try:
                movie = self.__get_movie(entry, session)
            except LookupError as e:
                log.debug(e)
            else:
                entry.update_using_map(self.movie_translate_map, movie)
        return entry

    def lazy_show_collected_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_collected'] = self.trakt.is_show_in_collection(self.__get_series(entry, session),
                                                                            entry['title'])
            except LookupError as e:
                log.debug(e)

        return entry

    def lazy_season_collected_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_collected'] = self.trakt.is_season_in_collection(self.__get_season(entry, session),
                                                                              entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_episode_collected_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_collected'] = self.trakt.is_episode_in_collection(self.__get_episode(entry, session),
                                                                               entry['title'])
            except LookupError as e:
                log.debug(e)

        return entry

    def lazy_movie_collected_lookup(self, entry):
        with Session() as session:

            try:
                entry['trakt_collected'] = self.trakt.is_movie_in_collection(self.__get_movie(entry, session),
                                                                             entry['title'])
            except LookupError as e:
                log.debug(e)

        return entry

    def lazy_show_watched_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_watched'] = self.trakt.is_show_watched(self.__get_series(entry, session), entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_season_watched_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_watched'] = self.trakt.is_season_watched(self.__get_season(entry, session), entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_episode_watched_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_watched'] = self.trakt.is_episode_watched(self.__get_episode(entry, session),
                                                                       entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_movie_watched_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_watched'] = self.trakt.is_movie_watched(self.__get_movie(entry, session), entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_show_user_ratings_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_series_user_rating'] = self.trakt.show_user_ratings(self.__get_series(entry, session),
                                                                                 entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_season_user_ratings_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_season_user_rating'] = self.trakt.season_user_ratings(self.__get_season(entry, session),
                                                                                   entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_episode_user_ratings_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_ep_user_rating'] = self.trakt.episode_user_ratings(self.__get_episode(entry, session),
                                                                                entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    def lazy_movie_user_ratings_lookup(self, entry):
        with Session() as session:
            try:
                entry['trakt_movie_user_rating'] = self.trakt.movie_user_ratings(self.__get_movie(entry, session),
                                                                                 entry['title'])
            except LookupError as e:
                log.debug(e)
        return entry

    # TODO: these shouldn't be here?
    def __entry_is_show(self, entry):
        return entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False)

    def __entry_is_episode(self, entry):
        return 'series_season' in entry and 'series_episode' in entry

    def __entry_is_season(self, entry):
        return 'series_season' in entry and not self.__entry_is_episode(entry)

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        if isinstance(config, bool):
            config = dict()

        for entry in task.entries:
            if self.__entry_is_show(entry):
                entry.register_lazy_func(self.lazy_series_lookup, self.series_map)
                # TODO cleaner way to do this?
                entry.register_lazy_func(self.lazy_series_actor_lookup, self.series_actor_map)
                entry.register_lazy_func(self.lazy_series_translate_lookup, self.show_translate_map)
                if self.__entry_is_episode(entry):
                    entry.register_lazy_func(self.lazy_episode_lookup, self.episode_map)
                elif self.__entry_is_season(entry):
                    entry.register_lazy_func(self.lazy_season_lookup, self.season_map)
            else:
                entry.register_lazy_func(self.lazy_movie_lookup, self.movie_map)
                # TODO cleaner way to do this?
                entry.register_lazy_func(self.lazy_movie_actor_lookup, self.movie_actor_map)
                entry.register_lazy_func(self.lazy_movie_translate_lookup, self.movie_translate_map)

            if config.get('username') or config.get('account'):
                self.__register_lazy_collected_lookup(entry)
                self.__register_lazy_watched_lookup(entry)
                self.__register_lazy_user_ratings_lookup(entry)

    def __register_lazy_collected_lookup(self, entry):
        if self.__entry_is_episode(entry):
            entry.register_lazy_func(self.lazy_episode_collected_lookup, ['trakt_collected'])
        elif self.__entry_is_season(entry):
            entry.register_lazy_func(self.lazy_season_collected_lookup, ['trakt_collected'])
        elif self.__entry_is_show(entry):
            entry.register_lazy_func(self.lazy_show_collected_lookup, ['trakt_collected'])
        else:
            entry.register_lazy_func(self.lazy_movie_collected_lookup, ['trakt_collected'])

    def __register_lazy_watched_lookup(self, entry):
        if self.__entry_is_episode(entry):
            entry.register_lazy_func(self.lazy_episode_watched_lookup, ['trakt_watched'])
        elif self.__entry_is_season(entry):
            entry.register_lazy_func(self.lazy_season_watched_lookup, ['trakt_watched'])
        elif self.__entry_is_show(entry):
            entry.register_lazy_func(self.lazy_show_watched_lookup, ['trakt_watched'])
        else:
            entry.register_lazy_func(self.lazy_movie_watched_lookup, ['trakt_watched'])

    def __register_lazy_user_ratings_lookup(self, entry):
        if self.__entry_is_show(entry):
            entry.register_lazy_func(self.lazy_show_user_ratings_lookup, ['trakt_series_user_rating'])
            entry.register_lazy_func(self.lazy_season_user_ratings_lookup, ['trakt_season_user_rating'])
            entry.register_lazy_func(self.lazy_episode_user_ratings_lookup, ['trakt_ep_user_rating'])
        else:
            entry.register_lazy_func(self.lazy_movie_user_ratings_lookup, ['trakt_movie_user_rating'])

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
    plugin.register(PluginTraktLookup, 'trakt_lookup', api_ver=2, interfaces=['task', 'series_metainfo',
                                                                              'movie_metainfo'])
