from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.utils.tools import split_title_year
from flexget.utils.log import log_once

log = logging.getLogger('bluray_lookup')


class PluginBlurayLookup(object):
    """Retrieves bluray information for entries.

    Example:
        tmdb_lookup: yes
    """

    field_map = {
        'bluray_name': 'name',
        'bluray_id': 'id',
        'bluray_year': 'year',
        'bluray_disc_rating': 'bluray_rating',
        'bluray_rating': 'rating',
        'bluray_studio': 'studio',
        # Make sure we don't store the db association proxy directly on the entry
        'bluray_genres': lambda movie: list(movie.genres),
        'bluray_released': 'release_date',
        'bluray_certification': 'certification',
        'bluray_runtime': 'runtime',
        'bluray_url': 'url',
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'name',
        'movie_year': 'year'
    }

    schema = {'type': 'boolean'}

    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        lookup = get_plugin_by_name('api_bluray').instance.lookup

        try:
            with Session() as session:
                title, year = split_title_year(entry['title'])
                movie = lookup(title=title,
                               year=year,
                               session=session)
                entry.update_using_map(self.field_map, movie)
        except LookupError:
            log_once('Bluray lookup failed for %s' % entry['title'], log, logging.WARN)

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
        return 'bluray_id'


@event('plugin.register')
def register_plugin():
    plugin.register(PluginBlurayLookup, 'bluray_lookup', api_ver=2, groups=['movie_metainfo'])
