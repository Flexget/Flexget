from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from functools import partial

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.log import log_once

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import extract_id
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')


log = logging.getLogger('tmdb_lookup')


class PluginTmdbLookup(object):
    """Retrieves tmdb information for entries.

    Example:
        tmdb_lookup: yes
    """

    field_map = {
        'tmdb_name': 'name',
        'tmdb_id': 'id',
        'imdb_id': 'imdb_id',
        'tmdb_year': 'year',
        'tmdb_popularity': 'popularity',
        'tmdb_rating': 'rating',
        # Make sure we don't stor the db association proxy directly on the entry
        'tmdb_genres': lambda movie: list(movie.genres),
        'tmdb_released': 'released',
        'tmdb_votes': 'votes',
        # Just grab the top 5 posters
        'tmdb_posters': lambda movie: [poster.url('original') for poster in movie.posters[:5]],
        'tmdb_backdrops': lambda movie: [poster.url('original') for poster in movie.backdrops[:5]],
        'tmdb_runtime': 'runtime',
        'tmdb_tagline': 'tagline',
        'tmdb_budget': 'budget',
        'tmdb_revenue': 'revenue',
        'tmdb_homepage': 'homepage',
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'name',
        'movie_year': 'year',
    }

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'object', 'properties': {'language': {'type': 'string', 'default': 'en'}}},
        ]
    }

    def lazy_loader(self, entry, language):
        """Does the lookup for this entry and populates the entry fields."""
        lookup = plugin.get('api_tmdb', self).lookup

        imdb_id = entry.get('imdb_id', eval_lazy=False) or extract_id(
            entry.get('imdb_url', eval_lazy=False)
        )
        try:
            with Session() as session:
                movie = lookup(
                    smart_match=entry['title'],
                    tmdb_id=entry.get('tmdb_id', eval_lazy=False),
                    imdb_id=imdb_id,
                    language=language,
                    session=session,
                )
                entry.update_using_map(self.field_map, movie)
        except LookupError:
            log_once('TMDB lookup failed for %s' % entry['title'], log, logging.WARN)

    def lookup(self, entry, language):
        """
        Populates all lazy fields to an Entry. May be called by other plugins
        requiring tmdb info on an Entry

        :param entry: Entry instance
        """
        lazy_func = partial(self.lazy_loader, language=language)
        entry.register_lazy_func(lazy_func, self.field_map)

    def on_task_metainfo(self, task, config):
        if not config:
            return
        language = config['language'] if not isinstance(config, bool) else 'en'

        for entry in task.entries:
            self.lookup(entry, language)

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'tmdb_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        PluginTmdbLookup, 'tmdb_lookup', api_ver=2, interfaces=['task', 'movie_metainfo']
    )
