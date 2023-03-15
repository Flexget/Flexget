from loguru import logger

from flexget import entry, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.log import log_once

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import extract_id
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')


logger = logger.bind(name='tmdb_lookup')


class PluginTmdbLookup:
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
        'tmdb_backdrops': lambda movie: [
            backdrop.url('original') for backdrop in movie.backdrops[:5]
        ],
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

    @entry.register_lazy_lookup('tmdb_lookup')
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
            log_once('TMDB lookup failed for %s' % entry['title'], logger, 'WARNING')

    def lookup(self, entry, language):
        """
        Populates all lazy fields to an Entry. May be called by other plugins
        requiring tmdb info on an Entry

        :param entry: Entry instance
        """
        entry.add_lazy_fields(self.lazy_loader, self.field_map, kwargs={'language': language})

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
