from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils import imdb
from flexget.utils.log import log_once

try:
    # TODO: Fix this after api_tmdb has module level functions
    from flexget.plugins.internal.api_tmdb import ApiTmdb

    lookup = ApiTmdb.lookup
except ImportError:
    raise plugin.DependencyError(issued_by='tmdb_lookup', missing='api_tmdb')

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
        'tmdb_certification': 'certification',
        'tmdb_posters': lambda movie: [poster.url for poster in movie.posters],
        'tmdb_runtime': 'runtime',
        'tmdb_tagline': 'tagline',
        'tmdb_budget': 'budget',
        'tmdb_revenue': 'revenue',
        'tmdb_homepage': 'homepage',
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'name',
        'movie_year': 'year'}

    schema = {'type': 'boolean'}

    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        imdb_id = (entry.get('imdb_id', eval_lazy=False) or
                   imdb.extract_id(entry.get('imdb_url', eval_lazy=False)))
        try:
            with Session() as session:
                movie = lookup(smart_match=entry['title'],
                               tmdb_id=entry.get('tmdb_id', eval_lazy=False),
                               imdb_id=imdb_id,
                               session=session)
                entry.update_using_map(self.field_map, movie)
        except LookupError:
            log_once('TMDB lookup failed for %s' % entry['title'], log, logging.WARN)

    def lookup(self, entry):
        """
        Populates all lazy fields to an Entry. May be called by other plugins
        requiring tmdb info on an Entry

        :param entry: Entry instance
        """
        entry.register_lazy_func(self.lazy_loader, self.field_map)

    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            self.lookup(entry)

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'tmdb_id'


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTmdbLookup, 'tmdb_lookup', api_ver=2, groups=['movie_metainfo'])
