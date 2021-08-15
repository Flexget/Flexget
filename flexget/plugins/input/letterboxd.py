from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, Session, TimedLimiter
from flexget.utils.soup import get_soup

logger = logger.bind(name='letterboxd')

requests = Session(max_retries=5)
requests.add_domain_limiter(TimedLimiter('letterboxd.com', '1 seconds'))
base_url = 'http://letterboxd.com'

SLUGS = {
    'default': {'p_slug': '/%(user)s/list/%(list)s/', 'f_slug': 'data-film-slug'},
    'diary': {'p_slug': '/%(user)s/films/diary/', 'f_slug': 'data-film-slug'},
    'likes': {'p_slug': '/%(user)s/likes/films/', 'f_slug': 'data-film-link'},
    'rated': {'p_slug': '/%(user)s/films/ratings/', 'f_slug': 'data-film-slug'},
    'watched': {'p_slug': '/%(user)s/films/', 'f_slug': 'data-film-slug'},
    'watchlist': {'p_slug': '/%(user)s/watchlist/', 'f_slug': 'data-film-slug'},
}

SORT_BY = {
    'default': '',
    'added': 'by/added/',
    'length-ascending': 'by/shortest/',
    'length-descending': 'by/longest/',
    'name': 'by/name/',
    'popularity': 'by/popular/',
    'rating-ascending': 'by/rating-lowest/',
    'rating-descending': 'by/rating/',
    'release-ascending': 'by/release-earliest/',
    'release-descending': 'by/release/',
}


class Letterboxd:
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'list': {'type': 'string'},
            'sort_by': {'type': 'string', 'enum': list(SORT_BY.keys()), 'default': 'default'},
            'max_results': {
                'type': 'integer',
                'deprecated': '`limit` plugin should be used instead of letterboxd `max_results` option',
            },
        },
        'required': ['username', 'list'],
        'additionalProperties': False,
    }

    def build_config(self, config):
        config['list'] = config['list'].lower().replace(' ', '-')
        list_key = config['list']
        if list_key not in list(SLUGS.keys()):
            list_key = 'default'
        config['p_slug'] = SLUGS[list_key]['p_slug'] % {
            'user': config['username'],
            'list': config['list'],
        }
        config['f_slug'] = SLUGS[list_key]['f_slug']
        config['sort_by'] = SORT_BY[config['sort_by']]

        return config

    def tmdb_lookup(self, search):
        if not search:
            logger.warning('Can\'t search tmdb, no tmdb_id')
            return

        try:
            tmdb = plugin.get('api_tmdb', self).lookup(tmdb_id=search)
        except LookupError as e:
            logger.warning('Error searching tmdb: {}', e)
            return

        result = {
            'title': '%s (%s)' % (tmdb.name, tmdb.year),
            'imdb_id': tmdb.imdb_id,
            'tmdb_id': tmdb.id,
            'movie_name': tmdb.name,
            'movie_year': tmdb.year,
        }

        return result

    def parse_film(self, film, config):
        url = base_url + film.get(config['f_slug'])
        soup = get_soup(requests.get(url).content)
        result = self.tmdb_lookup(soup.find(attrs={'data-tmdb-id': True}).get('data-tmdb-id'))
        if not result:
            return

        entry = Entry(result)
        entry['url'] = url
        entry['letterboxd_list'] = '%s (%s)' % (config['list'], config['username'])
        try:
            entry['letterboxd_score'] = float(soup.find(itemprop='average').get('content'))
        except AttributeError:
            pass
        if config['list'] == 'diary':
            entry['letterboxd_uscore'] = int(
                film.find_next(attrs={'data-rating': True}).get('data-rating')
            )
        elif config['list'] == 'rated':
            entry['letterboxd_uscore'] = int(film.find_next(itemprop='rating').get('content'))

        return entry

    @cached('letterboxd', persist='2 hours')
    def on_task_input(self, task, config=None):
        config = self.build_config(config)
        url = base_url + config['p_slug'] + config['sort_by']
        max_results = config.get('max_results', 1)
        rcount = 0
        next_page = ''

        logger.verbose('Looking for films in Letterboxd list: {}', url)

        while next_page is not None and rcount < max_results:
            try:
                page = requests.get(url).content
            except RequestException as e:
                raise plugin.PluginError('Error retrieving list from Letterboxd: %s' % e)
            soup = get_soup(page)

            for film in soup.find_all(attrs={config['f_slug']: True}):
                if rcount < max_results:
                    result = self.parse_film(film, config)
                    if not result:
                        continue
                    yield result
                    if 'max_results' in config:
                        rcount += 1

            next_page = soup.select_one('.paginate-nextprev .next')
            if next_page is not None:
                next_page = next_page.get('href')
                if next_page is not None:
                    url = base_url + next_page


@event('plugin.register')
def register_plugin():
    plugin.register(Letterboxd, 'letterboxd', api_ver=2)
