from __future__ import annotations

from collections.abc import MutableSet

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.requests import RequestException

logger = logger.bind(name='scrob_list')


class ScrobApiError(Exception):
    """Raised when the Scrob API returns a non-2xx response."""

    def __init__(self, message, status_code=None):
        self.status_code = status_code
        super().__init__(message)


class ScrobAPIWrapper:
    """Wrapper around a Scrob API's `/api/proxy/*` REST endpoints."""

    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _url(self, path):
        return f'{self.base_url}/api/proxy/{path.lstrip("/")}'

    def _request(self, method, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['X-Api-Key'] = self.api_key
        try:
            response = requests.request(
                method, self._url(path), headers=headers, raise_status=False, **kwargs
            )
        except RequestException as e:
            raise plugin.PluginError(f'Error connecting to Scrob at {self.base_url}: {e}')

        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}

        if not (200 <= response.status_code < 300):
            detail = data.get('detail') if isinstance(data, dict) else None
            raise ScrobApiError(
                detail or f'Scrob returned HTTP {response.status_code}',
                status_code=response.status_code,
            )
        return data

    def get(self, path, **kwargs):
        return self._request('get', path, **kwargs)

    def post(self, path, json=None, **kwargs):
        return self._request('post', path, json=json, **kwargs)

    def delete(self, path, **kwargs):
        return self._request('delete', path, **kwargs)


def _entry_media_type(entry):
    return 'series' if entry.get('series_name') else 'movie'


def _media_title(media, strip_year=False):
    title = media.get('title', 'Unknown')
    if strip_year:
        return title
    year = (media.get('release_date') or '')[:4]
    return f'{title} ({year})' if year else title


def _entry_from_item(item, strip_year=False):
    media = item['media']
    media_type = media.get('type')
    year = (media.get('release_date') or '')[:4]

    entry = Entry()
    entry['title'] = _media_title(media, strip_year=strip_year)
    if media_type == 'movie':
        entry['url'] = f'https://www.themoviedb.org/movie/{media.get("tmdb_id")}'
        entry['movie_name'] = media.get('title')
        if year:
            entry['movie_year'] = int(year)
    else:
        entry['url'] = f'https://www.themoviedb.org/tv/{media.get("tmdb_id")}'
        entry['series_name'] = media.get('title')
        if year:
            entry['series_year'] = int(year)

    entry['tmdb_id'] = media.get('tmdb_id')
    entry['scrob_list_item_id'] = item['id']
    entry['scrob_media_type'] = media_type

    return entry


class ScrobSet(MutableSet):
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string', 'format': 'url', 'default': 'http://localhost:7330'},
            'api_key': {'type': 'string'},
            'list_id': {'type': 'integer'},
            'strip_year': {'type': 'boolean', 'default': False},
        },
        'required': ['api_key', 'list_id'],
        'additionalProperties': False,
    }

    def __init__(self, config):
        self.config = config
        self.api = ScrobAPIWrapper(config['base_url'], config['api_key'])
        self.list_id = config['list_id']
        self._cached_items = None

    @property
    def immutable(self):
        return None

    def _get_items(self):
        try:
            result = self.api.get(f'lists/{self.list_id}')
        except ScrobApiError as e:
            if e.status_code == 404:
                raise plugin.PluginError(f'Scrob list {self.list_id} does not exist.')
            raise plugin.PluginError(f'Could not retrieve Scrob list: {e}')
        entries = []
        for item in result.get('items', []):
            media = item['media']
            if (
                media.get('type') not in ('movie', 'series')
                or media.get('season_number') is not None
            ):
                logger.debug(
                    'Skipping list item `%s` - not a whole movie or series.', media.get('title')
                )
                continue
            entry = _entry_from_item(item, strip_year=self.config.get('strip_year', False))
            if media.get('type') == 'movie':
                imdb_id = self._fetch_movie_imdb_id(media.get('tmdb_id'))
                if imdb_id:
                    entry['imdb_id'] = imdb_id
            entries.append(entry)
        return entries

    def _fetch_movie_imdb_id(self, tmdb_id):
        try:
            data = self.api.get(f'media/movie/{tmdb_id}')
        except ScrobApiError as e:
            logger.warning('Could not fetch imdb_id for tmdb_id %s from Scrob: %s', tmdb_id, e)
            return None
        return data.get('imdb_id')

    @property
    def items(self):
        if self._cached_items is None:
            self._cached_items = self._get_items()
        return self._cached_items

    def invalidate_cache(self):
        self._cached_items = None

    def _find_entry(self, entry):
        tmdb_id = entry.get('tmdb_id')
        if not tmdb_id:
            return None
        media_type = _entry_media_type(entry)
        for item in self.items:
            if item.get('tmdb_id') != tmdb_id:
                continue
            if item.get('scrob_media_type') != media_type:
                continue
            return item
        return None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def get(self, entry):
        return self._find_entry(entry)

    def add(self, entry):
        if self._find_entry(entry):
            return
        tmdb_id = entry.get('tmdb_id')
        if not tmdb_id:
            logger.warning('Not adding `%s` to Scrob list: entry has no tmdb_id.', entry['title'])
            return
        media_type = _entry_media_type(entry)
        body = {'tmdb_id': tmdb_id, 'media_type': media_type}
        try:
            self.api.post(f'lists/{self.list_id}/items', json=body)
        except ScrobApiError as e:
            if e.status_code == 409:
                logger.debug('`%s` is already in the Scrob list.', entry['title'])
            else:
                logger.error('Failed to add `%s` to Scrob list: %s', entry['title'], e)
                return
        self.invalidate_cache()

    def discard(self, entry):
        found = self._find_entry(entry)
        if not found:
            return
        try:
            self.api.delete(f'lists/{self.list_id}/items/{found["scrob_list_item_id"]}')
        except ScrobApiError as e:
            logger.error('Failed to remove `%s` from Scrob list: %s', entry['title'], e)
            return
        self.invalidate_cache()

    @property
    def online(self):
        """Web-based service - do not attempt to modify while running with --test."""
        return True


class ScrobList:
    schema = ScrobSet.schema

    def get_list(self, config):
        return ScrobSet(config)

    def on_task_input(self, task, config):
        return list(ScrobSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(ScrobList, 'scrob_list', api_ver=2, interfaces=['task', 'list'])
