from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.plugins.internal import api_rottentomatoes as plugin_api_rottentomatoes
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='api_rottentomatoes')

logger = logger.bind(name='rottentomatoes_list')


class RottenTomatoesList:
    """
    Emits an entry for each movie in a Rotten Tomatoes list.

    Configuration:

    dvds:
      - top_rentals
      - upcoming

    movies:
      - box_office

    Possible lists are
      * dvds: top_rentals, current_releases, new_releases, upcoming
      * movies: box_office, in_theaters, opening, upcoming
    """

    schema = {
        'type': 'object',
        'properties': {
            'dvds': {
                'type': 'array',
                'items': {'enum': ['top_rentals', 'current_releases', 'new_releases', 'upcoming']},
            },
            'movies': {
                'type': 'array',
                'items': {'enum': ['box_office', 'in_theaters', 'opening', 'upcoming']},
            },
            'api_key': {'type': 'string'},
        },
        'additionalProperties': False,
    }

    @cached('rottentomatoes_list', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        api_key = config.get('api_key', None)
        for l_type, l_names in list(config.items()):
            if not isinstance(l_names, list):
                continue

            for l_name in l_names:
                results = plugin_api_rottentomatoes.lists(
                    list_type=l_type, list_name=l_name, api_key=api_key
                )
                if results:
                    for movie in results['movies']:
                        if [entry for entry in entries if movie['title'] == entry.get('title')]:
                            continue
                        imdb_id = movie.get('alternate_ids', {}).get('imdb')
                        if imdb_id:
                            imdb_id = 'tt' + str(imdb_id)
                        entries.append(
                            Entry(
                                title=movie['title'],
                                rt_id=movie['id'],
                                imdb_id=imdb_id,
                                rt_name=movie['title'],
                                url=movie['links']['alternate'],
                            )
                        )
                else:
                    logger.critical(
                        "Failed to fetch Rotten tomatoes {} list: {}. List doesn't exist?",
                        l_type,
                        l_name,
                    )
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RottenTomatoesList, 'rottentomatoes_list', api_ver=2, interfaces=['task'])
