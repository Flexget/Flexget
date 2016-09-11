# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import functools

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
    trakt_series_banner_url
    trakt_series_fanart_url
    trakt_series_imdb_url
    trakt_series_trakt_url
    trakt_series_images
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
    trakt_ep_image_url
    trakt_ep_id
    trakt_ep_tvdb_id
    trakt_ep_images


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
        'trakt_series_url': lambda series: series.slug and 'http://trakt.tv/shows/%s' % series.slug,
        'trakt_series_country': 'country',
        'trakt_series_status': 'status',
        'trakt_series_overview': 'overview',
        'trakt_series_rating': 'rating',
        'trakt_series_votes': 'votes',
        'trakt_series_language': 'language',
        'trakt_series_aired_episodes': 'aired_episodes',
        'trakt_series_episodes': lambda show: [episodes.title for episodes in show.episodes],
        'trakt_series_poster_full': 'image_poster_full',
        'trakt_series_poster_medium': 'image_poster_medium',
        'trakt_series_poster_thumb': 'image_poster_thumb',
        'trakt_series_thumb': 'image_thumb_full',
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
        'trakt_ep_screenshot_full': 'image_screenshot_full',
        'trakt_ep_screenshot_medium': 'image_screenshot_medium',
        'trakt_ep_screenshot_thumb': 'image_screenshot_thumb',
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
        'trakt_fanart_full': 'image_fanart_full',
        'trakt_fanart_medium': 'image_fanart_medium',
        'trakt_fanart_thumb': 'image_fanart_thumb',
        'trakt_poster_full': 'image_poster_full',
        'trakt_poster_medium': 'image_poster_medium',
        'trakt_poster_thumb': 'image_poster_thumb',
        'trakt_logo': 'image_logo_full',
        'trakt_clearart': 'image_clearart_full',
        'trakt_banner': 'image_banner_full',
        'trakt_thumb': 'image_thumb_full'
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

    def lazy_series_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'title': entry.get('series_name', eval_lazy=False),
                          'year': entry.get('year', eval_lazy=False),
                          'trakt_id': entry.get('trakt_show_id', eval_lazy=False),
                          'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                          'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.series_map, series)
        return entry

    def lazy_series_actor_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'trakt_id': entry.get('trakt_show_id', eval_lazy=False),
                          'title': entry.get('series_name', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.series_actor_map, series)
        return entry

    def lazy_series_translate_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'trakt_id': entry.get('trakt_movie_id', eval_lazy=False),
                          'title': entry.get('series_name', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.show_translate_map, series)
        return entry

    def lazy_episode_lookup(self, entry):
        with Session(expire_on_commit=False) as session:
            lookupargs = {'title': entry.get('series_name', eval_lazy=False),
                          'trakt_id': entry.get('trakt_show_id', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
                episode = series.get_episode(entry['series_season'], entry['series_episode'], session)
            except LookupError as e:
                log.debug('Error looking up trakt episode information for %s: %s', entry['title'], e.args[0])
            else:
                entry.update_using_map(self.episode_map, episode)
        return entry

    def lazy_movie_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'title': entry.get('title', eval_lazy=False),
                          'year': entry.get('year', eval_lazy=False),
                          'trakt_id': entry.get('trakt_movie_id', eval_lazy=False),
                          'trakt_slug': entry.get('trakt_movie_slug', eval_lazy=False),
                          'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
                          'imdb_id': entry.get('imdb_id', eval_lazy=False),
                          'session': session}
            try:
                movie = lookup_movie(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.movie_map, movie)
        return entry

    def lazy_movie_actor_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'trakt_id': entry.get('trakt_movie_id', eval_lazy=False),
                          'title': entry.get('title', eval_lazy=False),
                          'session': session}
            try:
                movie = lookup_movie(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.movie_actor_map, movie)
        return entry

    def lazy_movie_translate_lookup(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'trakt_id': entry.get('trakt_movie_id', eval_lazy=False),
                          'title': entry.get('movie_name', eval_lazy=False),
                          'session': session}
            try:
                movie = lookup_movie(**lookupargs)
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry.update_using_map(self.movie_translate_map, movie)
        return entry

    def lazy_collected_lookup(self, config, style, entry):
        """Does the lookup for this entry and populates the entry fields."""
        if style == 'show' or style == 'episode':
            lookup = lookup_series
            trakt_id = entry.get('trakt_show_id', eval_lazy=True)
        else:
            lookup = lookup_movie
            trakt_id = entry.get('trakt_movie_id', eval_lazy=True)
        with Session() as session:
            lookupargs = {'trakt_id': trakt_id,
                          'session': session}
            try:
                item = lookup(**lookupargs)
                if style == 'episode':
                    item = item.get_episode(entry['series_season'], entry['series_episode'], session)
                collected = ApiTrakt.collected(style, item, entry.get('title'), username=config.get('username'),
                                               account=config.get('account'))
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry['trakt_collected'] = collected
        return entry

    def lazy_watched_lookup(self, config, style, entry):
        """Does the lookup for this entry and populates the entry fields."""
        if style == 'show' or style == 'episode':
            lookup = lookup_series
            trakt_id = entry.get('trakt_show_id', eval_lazy=True)
        else:
            lookup = lookup_movie
            trakt_id = entry.get('trakt_movie_id', eval_lazy=True)
        with Session() as session:
            lookupargs = {'trakt_id': trakt_id,
                          'session': session}
            try:
                item = lookup(**lookupargs)
                if style == 'episode':
                    item = item.get_episode(entry['series_season'], entry['series_episode'], session)
                watched = ApiTrakt.watched(style, item, entry.get('title'), username=config.get('username'),
                                           account=config.get('account'))
            except LookupError as e:
                log.debug(e.args[0])
            else:
                entry['trakt_watched'] = watched
        return entry

    def lazy_user_ratings_lookup(self, config, style, entry):
        """Does the ratings lookup for this entry and populates the entry fields."""
        if style in ['show', 'episode', 'season']:
            lookup = lookup_series
            trakt_id = entry.get('trakt_show_id', eval_lazy=True)
        else:
            lookup = lookup_movie
            trakt_id = entry.get('trakt_movie_id', eval_lazy=True)
        with Session() as session:
            lookupargs = {'trakt_id': trakt_id,
                          'session': session}
            try:
                item = lookup(**lookupargs)
                if style in ['show', 'episode', 'season']:
                    rating_style = style
                    if style == 'show':
                        rating_style = 'series'
                    elif style == 'episode':
                        rating_style = 'ep'
                    # fetch episode data if style is not series
                    if style in ['episode', 'season']:
                        item = item.get_episode(entry['series_season'], entry['series_episode'], session)
                    rating = ApiTrakt.user_ratings(style, item, entry.get('title'),
                                                   username=config.get('username'),
                                                   account=config.get('account'))
                    entry['trakt_{}_user_rating'.format(rating_style)] = rating
                else:
                    movie_rating = ApiTrakt.user_ratings(style, item, entry.get('title'),
                                                         username=config.get('username'),
                                                         account=config.get('account'))
                    entry['trakt_movie_user_rating'] = movie_rating
            except LookupError as e:
                log.debug(e.args[0])
        return entry

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        if isinstance(config, bool):
            config = dict()

        for entry in task.entries:
            if entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False):
                style = 'show'
                entry.register_lazy_func(self.lazy_series_lookup, self.series_map)
                # TODO cleaner way to do this?
                entry.register_lazy_func(self.lazy_series_actor_lookup, self.series_actor_map)
                entry.register_lazy_func(self.lazy_series_translate_lookup, self.show_translate_map)
                if 'series_season' in entry and 'series_episode' in entry:
                    entry.register_lazy_func(self.lazy_episode_lookup, self.episode_map)
                    style = 'episode'
            else:
                entry.register_lazy_func(self.lazy_movie_lookup, self.movie_map)
                # TODO cleaner way to do this?
                entry.register_lazy_func(self.lazy_movie_actor_lookup, self.movie_actor_map)
                entry.register_lazy_func(self.lazy_movie_translate_lookup, self.movie_translate_map)
                style = 'movie'

            if config.get('username') or config.get('account'):
                collected_lookup = functools.partial(self.lazy_collected_lookup, config, style)
                watched_lookup = functools.partial(self.lazy_watched_lookup, config, style)
                entry.register_lazy_func(collected_lookup, ['trakt_collected'])
                entry.register_lazy_func(watched_lookup, ['trakt_watched'])
                if style in ['show', 'episode']:
                    # register separate lazy calls to avoid fetching too much unnecessary data
                    entry.register_lazy_func(functools.partial(self.lazy_user_ratings_lookup, config, 'show'),
                                             ['trakt_series_user_rating'])
                    entry.register_lazy_func(functools.partial(self.lazy_user_ratings_lookup, config, 'season'),
                                             ['trakt_season_user_rating'])
                    entry.register_lazy_func(functools.partial(self.lazy_user_ratings_lookup, config, 'episode'),
                                             ['trakt_ep_user_rating'])
                else:
                    entry.register_lazy_func(functools.partial(self.lazy_user_ratings_lookup, config, style),
                                             ['trakt_movie_user_rating'])

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
    plugin.register(PluginTraktLookup, 'trakt_lookup', api_ver=3, groups=['series_metainfo', 'movie_metainfo'])
