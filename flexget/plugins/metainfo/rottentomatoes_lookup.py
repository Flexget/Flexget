from loguru import logger

from flexget import plugin
from flexget.entry import register_lazy_lookup
from flexget.event import event
from flexget.utils.log import log_once

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.plugins.internal import api_rottentomatoes as plugin_api_rottentomatoes
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='api_rottentomatoes')

logger = logger.bind(name='rottentomatoes_lookup')


def get_rt_url(movie):
    for link in movie.links:
        if link.name == 'alternate':
            return link.url


class PluginRottenTomatoesLookup:
    """
    Retrieves Rotten Tomatoes information for entries.

    Example::
        rottentomatoes_lookup: yes
    """

    field_map = {
        'rt_name': 'title',
        'rt_id': 'id',
        'rt_year': 'year',
        'rt_genres': lambda movie: [genre.name for genre in movie.genres],
        'rt_mpaa_rating': 'mpaa_rating',
        'rt_runtime': 'runtime',
        'rt_critics_consensus': 'critics_consensus',
        'rt_releases': lambda movie: {
            release.name: release.date for release in movie.release_dates
        },
        'rt_critics_rating': 'critics_rating',
        'rt_critics_score': 'critics_score',
        'rt_audience_rating': 'audience_rating',
        'rt_audience_score': 'audience_score',
        'rt_average_score': lambda movie: (movie.critics_score + movie.audience_score) / 2,
        'rt_synopsis': 'synopsis',
        'rt_posters': lambda movie: {poster.name: poster.url for poster in movie.posters},
        'rt_actors': lambda movie: [actor.name for actor in movie.cast],
        'rt_directors': lambda movie: [director.name for director in movie.directors],
        'rt_studio': 'studio',
        'rt_alternate_ids': lambda movie: {
            alt_id.name: alt_id.id for alt_id in movie.alternate_ids
        },
        'rt_url': get_rt_url,
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'title',
        'movie_year': 'year',
    }

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'string', 'description': 'provide a custom api key'},
        ]
    }

    def __init__(self):
        self.key = None

    @register_lazy_lookup('rottentomatoes_lookup')
    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields.

        :param entry: entry to perform lookup on
        :returns: the field value
        """
        try:
            self.lookup(entry, key=self.key)
        except plugin.PluginError as e:
            log_once(e.value.capitalize(), logger=logger)

    def lookup(self, entry, search_allowed=True, key=None):
        """
        Perform Rotten Tomatoes lookup for entry.

        :param entry: Entry instance
        :param search_allowed: Allow fallback to search
        :param key: optionally specify an API key to use
        :raises PluginError: Failure reason
        """
        if not key:
            key = self.key or plugin_api_rottentomatoes.API_KEY
        movie = plugin_api_rottentomatoes.lookup_movie(
            smart_match=entry['title'],
            rottentomatoes_id=entry.get('rt_id', eval_lazy=False),
            only_cached=(not search_allowed),
            api_key=key,
        )
        logger.debug('Got movie: {}', movie)
        entry.update_using_map(self.field_map, movie)

        if not entry.get('imdb_id', eval_lazy=False):
            for alt_id in movie.alternate_ids:
                if alt_id.name == 'imdb':
                    entry['imdb_id'] = 'tt' + alt_id.id
                    break

    def on_task_metainfo(self, task, config):
        if not config:
            return

        if isinstance(config, str):
            self.key = config.lower()
        else:
            self.key = None

        for entry in task.entries:
            entry.add_lazy_fields(self.lazy_loader, self.field_map)

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'rt_id'


@event('plugin.register')
def register_plugin():
    plugin.register(
        PluginRottenTomatoesLookup,
        'rottentomatoes_lookup',
        api_ver=2,
        interfaces=['task', 'movie_metainfo'],
    )
