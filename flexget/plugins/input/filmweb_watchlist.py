from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

try:
    from filmweb.exceptions import RequestFailed
    from filmweb.filmweb import Filmweb as FilmwebAPI
    from filmweb.items import LoggedUser
except ImportError:
    # Errors are handled later
    pass


logger = logger.bind(name='filmweb_watchlist')


def translate_type(type):
    return {'shows': 'serial', 'movies': 'film'}[type]


class FilmwebWatchlist:
    """Create an entry for each movie in your Filmweb list."""

    schema = {
        'type': 'object',
        'properties': {
            'login': {'type': 'string', 'description': 'Can be username or email address'},
            'password': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'movies'], 'default': 'movies'},
            'min_star': {
                'type': 'integer',
                'default': 0,
                'description': 'Items will be processed with at least this level of "How much I want to see"',
            },
        },
        'additionalProperties': False,
        'required': ['login', 'password'],
    }

    def on_task_start(self, task, config):
        """Raise a DependencyError if our dependencies aren't available."""
        try:
            from filmweb.filmweb import Filmweb as FilmwebAPI  # noqa: F401
        except ImportError as e:
            logger.debug('Error importing pyfilmweb: {}', e)
            raise plugin.DependencyError(
                'filmweb_watchlist',
                'pyfilmweb',
                f'pyfilmweb==0.1.1.1 module required. ImportError: {e}',
                logger,
            )

    @cached('filmweb_watchlist', persist='2 hours')
    def on_task_input(self, task, config):
        type = translate_type(config['type'])

        logger.verbose('Retrieving filmweb watch list for user: {}', config['login'])

        fw = FilmwebAPI()
        logger.verbose('Logging as {}', config['login'])

        try:
            fw.login(str(config['login']), str(config['password']))
        except RequestFailed as error:
            raise plugin.PluginError(f'Authentication request failed, reason {error!s}')

        user = LoggedUser(fw)

        try:
            watch_list = user.get_want_to_see()
        except RequestFailed as error:
            raise plugin.PluginError(f'Fetching watch list failed, reason {error!s}')

        logger.verbose('Filmweb list contains {} items', len(watch_list))

        entries = []
        for item in watch_list:
            if item['level'] < config['min_star']:
                continue

            if item['film'].type != type:
                continue

            item_info = item['film'].get_info()

            entry = Entry()
            entry['title'] = item_info['name_org'] or item_info['name']
            entry['title'] += ' ({})'.format(item_info['year'])
            entry['year'] = item_info['year']
            entry['url'] = item['film'].url
            entry['filmweb_type'] = item_info['type']
            entry['filmweb_id'] = item['film'].uid

            logger.debug('Created entry {}', entry)

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(FilmwebWatchlist, 'filmweb_watchlist', api_ver=2)
