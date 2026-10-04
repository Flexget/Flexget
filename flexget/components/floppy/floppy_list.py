from collections.abc import MutableSet

from loguru import logger

from flexget import plugin
from flexget.components.tmdb.api_tmdb import tmdb_request
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, Session
from flexget.utils.tools import split_title_year

logger = logger.bind(name='floppy_list')

# Floppy media types -> the kind of entry they become
KINDS = {'movie': 'movie', 'tv': 'show', 'anime': 'show', 'season': 'season', 'episode': 'episode'}
TYPE_KINDS = {'movies': 'movie', 'shows': 'show', 'seasons': 'season', 'episodes': 'episode'}
# Floppy addresses movies and shows by tmdb id only. Remember the ids resolved from tvdb/imdb.
_tmdb_id_cache = {}


def search_tmdb_id(entry, kind):
    """Return the tmdb id of the movie or show an entry names, or None."""
    if kind == 'movie':
        name, year = entry.get('movie_name'), entry.get('movie_year')
        endpoint, year_param, title_keys = 'search/movie', 'year', ['title', 'original_title']
    else:
        name, year = split_title_year(entry.get('series_name') or '')
        endpoint, year_param = 'search/tv', 'first_air_date_year'
        title_keys = ['name', 'original_name']
    if not name:
        return None
    cache_key = (endpoint, name.lower(), year)
    if cache_key not in _tmdb_id_cache:
        params = {'query': name}
        if year:
            params[year_param] = year
        try:
            results = tmdb_request(endpoint, **params).get('results') or []
        except RequestException as e:
            logger.warning('Error searching for {} on tmdb: {}', name, e)
            return None
        # tmdb sorts by relevance, but prefer a result with exactly the name asked for
        exact = [
            result
            for result in results
            if name.lower() in [(result.get(key) or '').lower() for key in title_keys]
        ]
        found = (exact or results or [None])[0]
        if found:
            logger.verbose(
                'Found tmdb id {} for `{}` by searching for its name', found['id'], name
            )
        _tmdb_id_cache[cache_key] = found['id'] if found else None
    return _tmdb_id_cache[cache_key]


def find_tmdb_id(entry, kind):
    """Return the tmdb id of the movie or show an entry is about, or None.

    Ids already on the entry are preferred, then ids from lazy lookups, then a search by name.

    :param entry: The entry to find the id for.
    :param kind: ``movie`` or ``show``. For a season or episode, the id of its show is returned.
    """
    results_key = 'movie_results' if kind == 'movie' else 'tv_results'
    if entry.get('tmdb_id', eval_lazy=False):
        return entry['tmdb_id']
    # On a series entry a lazy tmdb_id or imdb_id may come from a movie lookup, and tmdb cannot
    # look a movie up by tvdb id
    fields = [('imdb_id', True)] if kind == 'movie' else [('tvdb_id', True), ('imdb_id', False)]
    for field, lazy in fields:
        external_id = entry.get(field, eval_lazy=lazy)
        if not external_id:
            continue
        cache_key = (results_key, field, external_id)
        if cache_key not in _tmdb_id_cache:
            try:
                result = tmdb_request(f'find/{external_id}', external_source=field)
            except RequestException as e:
                logger.warning('Error looking up {} {} on tmdb: {}', field, external_id, e)
                continue
            found = result.get(results_key) or []
            _tmdb_id_cache[cache_key] = found[0]['id'] if found else None
        if _tmdb_id_cache[cache_key]:
            return _tmdb_id_cache[cache_key]
    if kind == 'movie' and entry.get('tmdb_id'):
        return entry['tmdb_id']
    return search_tmdb_id(entry, kind)


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


class FloppySet(MutableSet):
    """A list or the collection of a Floppy server, as a set of entries.

    Floppy lists hold movies, shows and seasons. The ``collection`` list is the media the user
    owns, and holds movies and episodes. Floppy identifies all of them by tmdb id, so an entry
    needs a ``tmdb_id``, or a ``tvdb_id`` or ``imdb_id`` it can be resolved from, to be submitted.

    :param config: The ``floppy_list`` plugin configuration, see :class:`FloppyList`.
    """

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string', 'format': 'url'},
            'api_key': {'type': 'string'},
            'list': {'type': 'string'},
            'type': {
                'type': 'string',
                'enum': ['shows', 'seasons', 'episodes', 'movies', 'auto'],
                'default': 'auto',
            },
            'strip_dates': {'type': 'boolean', 'default': False},
        },
        'required': ['base_url', 'api_key', 'list'],
        'additionalProperties': False,
    }

    @property
    def immutable(self):
        return None

    def __init__(self, config):
        self.config = config
        self.config.setdefault('type', 'auto')
        self.base_url = self.config['base_url'].rstrip('/')
        self.session = Session()
        self.session.headers.update({'Authorization': 'Bearer {}'.format(self.config['api_key'])})
        self._cached_items = None
        self._list_id = None

    @property
    def is_collection(self):
        return self.config['list'].lower() == 'collection'

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def add(self, entry):
        self.submit([entry])

    def __ior__(self, entries):
        # Optimization to submit multiple entries at same time
        self.submit(entries)
        return self

    def discard(self, entry):
        self.submit([entry], remove=True)

    def __isub__(self, entries):
        # Optimization to submit multiple entries at same time
        self.submit(entries, remove=True)
        return self

    def _find_entry(self, entry):
        for item in self.items:
            # An item only matches as what it is: an episode in the list must not match every
            # episode of its season, but a show or season in the list matches all its episodes.
            if item.get('series_episode') is not None:
                match = self.episode_match
            elif item.get('series_season') is not None:
                match = self.season_match
            elif item.get('series_name'):
                match = self.show_match
            else:
                match = self.movie_match
            if match(entry, item):
                return item
        return None

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def clear(self):
        if self.items:
            self.submit(list(self.items), remove=True)
            self._cached_items = None

    def get(self, entry):
        return self._find_entry(entry)

    # -- Public interface ends here -- #

    def request(self, method, endpoint, **kwargs):
        url = '{}/api/v1/{}/'.format(self.base_url, '/'.join(str(part) for part in endpoint))
        return self.session.request(method, url, raise_status=False, **kwargs)

    def get_pages(self, endpoint):
        """Iterate over the results of a paginated floppy endpoint."""
        offset = 0
        while True:
            result = self.request('get', endpoint, params={'limit': 200, 'offset': offset})
            if result.status_code == 404:
                raise plugin.PluginError(
                    'List does not appear to exist on floppy: {}'.format(self.config['list'])
                )
            if result.status_code in [401, 403]:
                raise plugin.PluginError(
                    'Authentication error: check the floppy `api_key` and its permissions.'
                )
            if result.status_code != 200:
                raise plugin.PluginError(f'Error getting data from floppy: {result.text}')
            try:
                data = result.json()
            except ValueError:
                logger.debug('Could not decode json from response: {}', result.text)
                raise plugin.PluginError('Error getting list from floppy.')
            yield from data['results']
            if not data['pagination'].get('next'):
                return
            offset += data['pagination']['limit']

    @property
    def list_id(self):
        if self._list_id is None:
            for floppy_list in self.get_pages(('lists',)):
                if floppy_list['name'].lower() == self.config['list'].lower():
                    self._list_id = floppy_list['id']
                    break
            else:
                raise plugin.PluginError(
                    'List does not appear to exist on floppy: {}'.format(self.config['list'])
                )
        return self._list_id

    def get_list_endpoint(self):
        if self.is_collection:
            return ('collection',)
        return ('lists', self.list_id, 'items')

    def get_items(self):
        """Iterate over retrieved items from the floppy api."""
        logger.verbose('Retrieving `{}` list `{}`', self.config['type'], self.config['list'])
        try:
            items = [row['item'] for row in self.get_pages(self.get_list_endpoint())]
        except RequestException as e:
            raise plugin.PluginError(f'Could not retrieve list from floppy ({e})')

        # Seasons and episodes only carry the id of their show, so take its name from the list.
        show_titles = {
            (item['source'], item['media_id']): self.generate_title(item)
            for item in items
            if KINDS.get(item['media_type']) == 'show'
        }
        for item in items:
            kind = KINDS.get(item['media_type'])
            if kind is None:
                logger.debug('Skipping {} because it is a {}', item['title'], item['media_type'])
                continue
            if self.config['type'] != 'auto' and TYPE_KINDS[self.config['type']] != kind:
                logger.debug('Skipping {} because it is not a {}', item['title'], kind)
                continue
            if not item['title']:
                logger.warning('Item in floppy list does not appear to have a title, skipping.')
                continue
            yield self.entry_from_item(item, kind, show_titles)

    def generate_title(self, item):
        year = (item.get('release_datetime') or '')[:4]
        if year and not self.config.get('strip_dates'):
            return '{} ({})'.format(item['title'], year)
        return item['title']

    def entry_from_item(self, item, kind, show_titles):
        entry = Entry()
        url = '{}{}'.format(
            self.base_url,
            item.get('url')
            or '/details/{}/{}/{}'.format(item['source'], item['media_type'], item['media_id']),
        )
        # Seasons and episodes share the page of their show, but every entry needs its own url
        if kind == 'season':
            url += '#S{:02d}'.format(item['season_number'])
        elif kind == 'episode':
            url += '#S{:02d}E{:02d}'.format(item['season_number'], item['episode_number'])
        entry['url'] = url
        ids = dict(item.get('ids') or {})
        if item['source'] in ['tmdb', 'tvdb']:
            ids[item['source']] = item['media_id']
        if kind in ['season', 'episode']:
            # The other ids of a season or episode item are not the show's
            ids = {'tmdb': ids.get('tmdb')} if item['source'] == 'tmdb' else {}
        for name, value in ids.items():
            if value:
                entry[f'{name}_id'] = as_int(value)

        if kind == 'movie':
            entry['title'] = self.generate_title(item)
            entry['movie_name'] = item['title']
            year = (item.get('release_datetime') or '')[:4]
            if year:
                entry['movie_year'] = int(year)
            return entry

        if kind == 'show':
            entry['title'] = entry['series_name'] = self.generate_title(item)
            return entry

        series_name = show_titles.get((item['source'], item['media_id']), item['title'])
        entry['series_name'] = series_name
        entry['series_season'] = item['season_number']
        if kind == 'season':
            entry['title'] = '{} S{:02d}'.format(series_name, item['season_number'])
            return entry

        entry['series_episode'] = item['episode_number']
        entry['series_id'] = 'S{:02d}E{:02d}'.format(item['season_number'], item['episode_number'])
        entry['title'] = '{} {}'.format(series_name, entry['series_id'])
        return entry

    @property
    def items(self):
        if self._cached_items is None:
            self._cached_items = list(self.get_items())
        return self._cached_items

    def invalidate_cache(self):
        self._cached_items = None

    def show_match(self, entry1, entry2):
        if not entry1.get('series_name'):
            return False
        if any(
            entry1.get(ident) is not None and entry1[ident] == entry2.get(ident)
            for ident in ['tmdb_id', 'tvdb_id', 'imdb_id']
        ):
            return True
        if not (entry1.get('series_name') and entry2.get('series_name')):
            return False
        # Floppy only knows the year of a show when the show itself is in the list
        name1, year1 = split_title_year(entry1['series_name'])
        name2, year2 = split_title_year(entry2['series_name'])
        return name1.lower() == name2.lower() and (not year1 or not year2 or year1 == year2)

    def season_match(self, entry1, entry2):
        return (
            self.show_match(entry1, entry2)
            and entry1.get('series_season') is not None
            and entry1['series_season'] == entry2.get('series_season')
        )

    def episode_match(self, entry1, entry2):
        return (
            self.season_match(entry1, entry2)
            and entry1.get('series_episode') is not None
            and entry1['series_episode'] == entry2.get('series_episode')
        )

    def movie_match(self, entry1, entry2):
        # tmdb ids of movies and shows overlap, so an id alone does not tell them apart
        if entry1.get('series_name') or entry2.get('series_name'):
            return False
        if any(
            entry1.get(id) is not None and entry1[id] == entry2.get(id)
            for id in ['imdb_id', 'tmdb_id']
        ):
            return True
        return bool(
            entry1.get('movie_name')
            and (entry1.get('movie_name'), entry1.get('movie_year'))
            == (entry2.get('movie_name'), entry2.get('movie_year'))
        )

    def get_submit_endpoint(self, entry):
        """Return the floppy endpoint an entry is added to or removed from, or None.

        With ``type: auto`` the most specific thing the entry describes is submitted: an episode,
        else a season, else a show, else a movie. Lists do not take episodes, and the collection
        does not take shows or seasons.
        """
        list_type = self.config['type']
        if list_type in ['auto', 'shows', 'seasons', 'episodes'] and entry.get('series_name'):
            season = entry.get('series_season')
            episode = entry.get('series_episode')
            if list_type in ['auto', 'episodes'] and season is not None and episode is not None:
                kind = 'episode'
            elif list_type in ['auto', 'seasons'] and season is not None:
                kind = 'season'
            elif list_type in ['auto', 'shows']:
                kind = 'show'
            else:
                logger.debug('Not submitting `{}`, no {} found.', entry['title'], list_type[:-1])
                return None
        elif list_type in ['auto', 'movies']:
            kind = 'movie'
        else:
            return None

        # Floppy collects shows per episode, and its lists do not hold single episodes
        if self.is_collection and kind in ['show', 'season']:
            logger.warning(
                'Not submitting `{}`, floppy collection only takes movies and episodes.',
                entry['title'],
            )
            return None
        if not self.is_collection and kind == 'episode':
            logger.warning(
                'Not submitting `{}`, floppy lists do not take episodes. '
                'Set `type` to `shows` or `seasons` to submit its show or season.',
                entry['title'],
            )
            return None

        tmdb_id = find_tmdb_id(entry, 'movie' if kind == 'movie' else 'show')
        if not tmdb_id:
            logger.warning('Not submitting `{}`, no tmdb id found.', entry['title'])
            return None

        endpoint = ('media', 'movie' if kind == 'movie' else 'tv', 'tmdb', tmdb_id)
        if kind in ['season', 'episode']:
            endpoint += (entry['series_season'],)
        if kind == 'episode':
            endpoint += ('episodes', entry['series_episode'])
        if self.is_collection:
            return (*endpoint, 'collection')
        return (*endpoint, 'lists', self.list_id)

    def submit(self, entries, remove=False):
        """Submit movies, shows or episodes to the floppy api."""
        action = 'deleted' if remove else 'added'
        changed = 0
        for entry in entries:
            endpoint = self.get_submit_endpoint(entry)
            if endpoint is None:
                continue
            kwargs = {}
            if self.is_collection and not remove:
                quality = entry.get('quality')
                resolution = getattr(quality, 'resolution', None)
                kwargs['json'] = {'resolution': resolution.name} if resolution else {}
            logger.debug('Submitting data to floppy ({}): {}', endpoint, kwargs)
            try:
                result = self.request('delete' if remove else 'put', endpoint, **kwargs)
            except RequestException as e:
                logger.error('Error submitting data to floppy: {}', e)
                return
            if 200 <= result.status_code < 300:
                changed += 1
            elif result.status_code == 409:
                logger.debug('`{}` is already in list {}', entry['title'], self.config['list'])
            elif result.status_code == 404:
                logger.debug('floppy did not find `{}`: {}', entry['title'], result.text)
            elif result.status_code in [401, 403]:
                logger.error(
                    'Authentication error: check the floppy `api_key` and its permissions.'
                )
                logger.debug('floppy response: {}', result.text)
                return
            else:
                logger.error('Unknown error submitting data to floppy: {}', result.text)

        if changed:
            logger.info(
                'Successfully {} to/from list {}: {} item(s).',
                action,
                self.config['list'],
                changed,
            )
            # Mark the results expired if we added or removed anything
            self.invalidate_cache()

    @property
    def online(self):
        """Set the online status of the plugin.

        Online plugin should be treated differently in certain situations, like test mode
        """
        return True


class FloppyList:
    """Use the lists and the collection of a Floppy server, a self-hosted media tracker.

    Can be used as an input, and with the list plugins (``list_add``, ``list_remove``,
    ``list_match``, ``list_clear``).

    Options:

    ``base_url``
        Address of the Floppy server.
    ``api_key``
        A Floppy app token. Needs the ``lists:read`` and ``lists:write`` permissions for lists,
        ``watchlist:read`` and ``watchlist:write`` for the collection.
    ``list``
        Name of a Floppy list, or ``collection`` for the media the user owns.
    ``type``
        One of ``movies``, ``shows``, ``seasons``, ``episodes`` or ``auto`` (default).
    ``strip_dates``
        Do not add the year to titles. Defaults to no.

    Example, download the movies of a Floppy list::

        floppy_list:
          base_url: http://localhost:8000
          api_key: flp_xxxxxxxx
          list: To Download
          type: movies

    Example, mark accepted movies and episodes as collected::

        list_add:
          - floppy_list:
              base_url: http://localhost:8000
              api_key: flp_xxxxxxxx
              list: collection
    """

    schema = FloppySet.schema

    def get_list(self, config):
        return FloppySet(config)

    # TODO: we should somehow invalidate this cache when the list is modified
    @cached('floppy_list', persist='2 hours')
    def on_task_input(self, task, config):
        # We use the generator here rather than the cached list in case limit plugin is used.
        return FloppySet(config).get_items()


@event('plugin.register')
def register_plugin():
    plugin.register(FloppyList, 'floppy_list', api_ver=2, interfaces=['task', 'list'])
