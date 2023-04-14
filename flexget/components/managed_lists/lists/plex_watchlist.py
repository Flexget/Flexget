import typing
from collections.abc import MutableSet
from typing import List, Optional, Type, Union

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

PLUGIN_NAME = 'plex_watchlist'
SUPPORTED_IDS = ['imdb_id', 'tmdb_id', 'tvdb_id', 'plex_guid']

logger = logger.bind(name=PLUGIN_NAME)

if typing.TYPE_CHECKING:
    from plexapi.myplex import MyPlexAccount
    from plexapi.video import Movie, Show


def import_plexaccount() -> "Type[MyPlexAccount]":
    try:
        from plexapi.myplex import MyPlexAccount

        return MyPlexAccount
    except ImportError:
        raise plugin.DependencyError('plex_watchlist', 'plexapi', 'plexapi package required')


def to_entry(plex_item: "Union[Movie, Show]") -> Entry:
    entry = Entry(
        title=f"{plex_item.title} ({plex_item.year})" if plex_item.year else plex_item.title,
        url=plex_item.guid,
    )

    if plex_item.TYPE == 'movie':
        entry['movie_name'] = plex_item.title
        entry['movie_year'] = plex_item.year
    elif plex_item.TYPE == 'show':
        entry['series_name'] = plex_item.title
        entry['series_year'] = plex_item.year

    entry.update(get_supported_ids_from_plex_object(plex_item))

    return entry


def get_supported_ids_from_plex_object(plex_item):
    ids = {'plex_guid': plex_item.guid}
    for guid in plex_item.guids:
        x = guid.id.split("://")
        try:
            value = int(x[1])
        except ValueError:
            value = x[1]

        media_id = f'{x[0]}_id'
        if media_id in SUPPORTED_IDS:
            ids[media_id] = value
    return ids


class VideoStub:
    guid: str
    title: str


# plexapi objects are build fomr XML. So we create a simple stub that works for watchlist calls
def to_plex_item(entry):
    item = VideoStub()
    item.guid = entry['plex_guid']
    item.title = entry['title']
    return item


class PlexManagedWatchlist(MutableSet):
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        filter: Optional[str] = None,
        type: Optional[str] = None,
    ):
        self.username = username
        self.password = password
        self.token = token
        self.type = type
        self.filter = filter
        self._items: Optional[List[Entry]] = None
        self._account: Optional[MyPlexAccount] = None

    @property
    def account(self) -> "MyPlexAccount":
        MyPlexAccount = import_plexaccount()
        if self._account is None:
            self._account = MyPlexAccount(self.username, self.password, self.token)
        return self._account

    @property
    def items(self) -> List[Entry]:
        if self._items is None:
            watchlist = self.account.watchlist(filter=self.filter, libtype=self.type)
            self._items = []
            for item in watchlist:
                self._items.append(to_entry(item))
        return self._items

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, entry) -> bool:
        return self._find_entry(entry) is not None

    def get(self, entry) -> Optional[Entry]:
        return self._find_entry(entry)

    def add(self, entry: Entry) -> None:
        item = None

        if 'plex_guid' in entry:
            item = to_plex_item(entry)
        else:
            logger.debug('Searching for {} with discover', entry['title'])
            results = self.account.searchDiscover(entry['title'], libtype=self.type)
            matched_entry = self._match_entry(entry, [to_entry(result) for result in results])
            if matched_entry:
                item = to_plex_item(matched_entry)

        if item:
            if self.account.onWatchlist(item):
                logger.debug(f'"{item.title}" is already on the watchlist')
                return

            logger.debug(f'Adding "{item.title}" to the watchlist')
            self.account.addToWatchlist(item)

    def discard(self, entry) -> None:
        entry = self._find_entry(entry)
        if entry:
            item = to_plex_item(entry)
            logger.debug('Removing {} from watchlist', entry['title'])
            self.account.removeFromWatchlist(item)

    @property
    def online(self) -> bool:
        return True

    @property
    def immutable(self):
        return False

    def _find_entry(self, entry):
        return self._match_entry(entry, self.items)

    def _match_entry(self, entry: Entry, entries: List[Entry]):
        for item in entries:
            # match on supported ids
            if any(entry.get(id) is not None and entry[id] == item[id] for id in SUPPORTED_IDS):
                return item

            name = entry.get('movie_name', None) or entry.get('series_name', None)
            year = entry.get('movie_year', None) or entry.get('series_year', None)
            _name = item.get('movie_name', None) or item.get('series_name', None)
            _year = item.get('movie_year', None) or item.get('series_year', None)
            if (name and year) and (_name == name and _year == year):
                return item

            # title matching sucks but lets try as last resort
            if entry.get('title').lower() == item['title'].lower():
                return item


class PlexWatchlist:
    schema = {
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'token': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['movie', 'show']},
            'filter': {'type': 'string', 'enum': ['available', 'released']},
        },
        'anyOf': [{'required': ['token']}, {'required': ['username', 'password']}],
    }

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        import_plexaccount()

    def get_list(self, config):
        return PlexManagedWatchlist(**config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        yaml_list = PlexManagedWatchlist(**config)
        yield from yaml_list


@event('plugin.register')
def register_plugin():
    plugin.register(PlexWatchlist, PLUGIN_NAME, api_ver=2, interfaces=['task', 'list'])
