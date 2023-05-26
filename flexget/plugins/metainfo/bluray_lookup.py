from loguru import logger

from flexget import plugin
from flexget.entry import register_lazy_lookup
from flexget.event import event
from flexget.manager import Session
from flexget.utils.log import log_once
from flexget.utils.tools import split_title_year

logger = logger.bind(name='bluray_lookup')


class PluginBlurayLookup:
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
        'movie_year': 'year',
    }

    schema = {'type': 'boolean'}

    @register_lazy_lookup('bluray_lookup')
    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        lookup = plugin.get('api_bluray', self).lookup

        try:
            with Session() as session:
                title, year = split_title_year(entry['title'])
                movie = lookup(title=title, year=year, session=session)
                entry.update_using_map(self.field_map, movie)
        except LookupError:
            log_once('Bluray lookup failed for %s' % entry['title'], logger, 'WARNING')

    def lookup(self, entry):
        """
        Populates all lazy fields to an Entry. May be called by other plugins
        requiring bluray info on an Entry

        :param entry: Entry instance
        """
        entry.add_lazy_fields(self.lazy_loader, self.field_map)

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
    plugin.register(
        PluginBlurayLookup, 'bluray_lookup', api_ver=2, interfaces=['task', 'movie_metainfo']
    )
