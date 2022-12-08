import typing
from collections.abc import MutableSet
from typing import List, Optional, Type, Union

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

PLUGIN_NAME = 'plex_watchlist'
SUPPORTED_IDS = ['imdb_id', 'tmdb_id', 'tvdb_id']

logger = logger.bind(name=PLUGIN_NAME)

if typing.TYPE_CHECKING:
    from plexapi.myplex import MyPlexAccount
    from plexapi.video import Movie, Show


def import_plexaccount() -> "Type[MyPlexAccount]":
    try:
        from plexapi.myplex import MyPlexAccount  # noqa
    except ImportError:
        raise plugin.DependencyError('plex_watchlist', 'plexapi', 'plexapi package required')
    return MyPlexAccount


def create_entry(plex_item: "Union[Movie, Show]") -> Entry:
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

    for guid in plex_item.guids:
        x = guid.id.split("://")
        try:
            value = int(x[1])
        except ValueError:
            value = x[1]

        media_id = f'{x[0]}_id'
        if media_id in SUPPORTED_IDS:
            entry[media_id] = value

    return entry


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

    @property
    def account(self) -> "MyPlexAccount":
        MyPlexAccount = import_plexaccount()
        return MyPlexAccount(self.username, self.password, self.token)

    @property
    def items(self) -> List[Entry]:
        if self._items is None:
            watchlist = self.account.watchlist(filter=self.filter, libtype=self.type)
            self._items = []
            for item in watchlist:
                self._items.append(create_entry(item))
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
        raise NotImplemented
        self.account.addToWatchlist()

    def discard(self, entry) -> None:
        raise NotImplemented
        self.account.removeFromWatchlist()

    @property
    def online(self) -> bool:
        return True

    @property
    def immutable(self) -> bool:
        # TODO: Turn this true after the editing is implemented
        return True

    def _find_entry(self, entry):
        for item in self.items:
            for sid in SUPPORTED_IDS:
                if sid in item and sid in entry:
                    if item[sid] == entry[sid]:
                        return item
                    break

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
        for item in yaml_list:
            yield item


@event('plugin.register')
def register_plugin():
    plugin.register(PlexWatchlist, PLUGIN_NAME, api_ver=2, interfaces=['task', 'list'])
