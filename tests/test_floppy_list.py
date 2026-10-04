import re

import pytest

from flexget.components.floppy import floppy_list
from flexget.components.floppy.floppy_list import FloppySet
from flexget.entry import Entry, register_lazy_lookup
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException

BASE_URL = 'http://floppy.test'
API_KEY = 'flp_test'


def floppy_item(media_type, media_id, title, season=None, episode=None, year=None, ids=None):
    return {
        'media_id': str(media_id),
        'source': 'tmdb',
        'media_type': media_type,
        'title': title,
        'url': f'/details/tmdb/{media_type}/{media_id}/slug',
        'ids': ids or {},
        'season_number': season,
        'episode_number': episode,
        'release_datetime': f'{year}-01-01T00:00:00Z' if year else None,
    }


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        if self._data is ValueError:
            raise ValueError('not json')
        return self._data


class FakeFloppy:
    """Answers the floppy endpoints the plugin uses, and records what was submitted."""

    page_size = 2

    def __init__(self):
        self.lists = {1: ('To Download', []), 2: ('Empty', [])}
        self.collection = []
        self.calls = []
        self.tmdb_calls = []
        # path -> response to return, or exception to raise, instead of the normal answer
        self.overrides = {}
        # Answer to every submit, when set
        self.submit_response = None
        # endpoint -> answer of tmdb, or exception to raise, instead of the normal answer
        self.tmdb_overrides = {}

    def page(self, rows, params):
        offset = params['offset']
        end = offset + self.page_size
        return FakeResponse(
            200,
            {
                'pagination': {'limit': self.page_size, 'next': end < len(rows) or None},
                'results': rows[offset:end],
            },
        )

    def request(self, session, method, url, **kwargs):
        assert session.headers['Authorization'] == f'Bearer {API_KEY}'
        assert url.startswith(f'{BASE_URL}/api/v1/')
        path = url[len(f'{BASE_URL}/api/v1/') :].strip('/')
        if path in self.overrides:
            if isinstance(self.overrides[path], Exception):
                raise self.overrides[path]
            return self.overrides[path]
        if method == 'get':
            if path == 'lists':
                rows = [{'id': id, 'name': name} for id, (name, _) in self.lists.items()]
                return self.page(rows, kwargs['params'])
            if path == 'collection':
                return self.page([{'item': item} for item in self.collection], kwargs['params'])
            match = re.fullmatch(r'lists/(\d+)/items', path)
            items = self.lists[int(match.group(1))][1]
            return self.page([{'item': item} for item in items], kwargs['params'])
        self.calls.append((method, path, kwargs.get('json')))
        if self.submit_response is not None:
            return self.submit_response
        if method == 'delete':
            return FakeResponse(204)
        return FakeResponse(201 if path.endswith('collection') else 200, {})


@pytest.fixture
def floppy(monkeypatch):
    fake = FakeFloppy()

    def request(session, method, url, **kwargs):
        return fake.request(session, method, url, **kwargs)

    monkeypatch.setattr('flexget.utils.requests.Session.request', request)
    monkeypatch.setattr(floppy_list, '_tmdb_id_cache', {})

    def tmdb_request(endpoint, **params):
        fake.tmdb_calls.append((endpoint, params))
        if endpoint in fake.tmdb_overrides:
            if isinstance(fake.tmdb_overrides[endpoint], Exception):
                raise fake.tmdb_overrides[endpoint]
            return fake.tmdb_overrides[endpoint]
        if endpoint == 'search/tv':
            return {
                'results': [
                    {'id': 999, 'name': 'Breaking Bad: The Aftershow'},
                    {'id': 1396, 'name': 'Breaking Bad'},
                ]
            }
        if endpoint == 'search/movie':
            return {'results': [{'id': 603, 'title': 'The Matrix'}]}
        return {'tv_results': [{'id': 1396}], 'movie_results': []}

    monkeypatch.setattr(floppy_list, 'tmdb_request', tmdb_request)
    return fake


class TestFloppyList:
    config = f"""
      templates:
        global:
          disable: [seen]
      tasks:
        read_list:
          floppy_list: &to_download
            base_url: {BASE_URL}
            api_key: {API_KEY}
            list: to download
        read_collection:
          floppy_list: &collection
            base_url: {BASE_URL}
            api_key: {API_KEY}
            list: collection
        add_to_list:
          mock:
            - {{title: 'The Matrix (1999)', movie_name: 'The Matrix', tmdb_id: 603}}
            - {{title: 'Breaking Bad', series_name: 'Breaking Bad', tvdb_id: 81189}}
          accept_all: yes
          list_add:
            - floppy_list: *to_download
        add_episode_to_list:
          mock:
            - title: Breaking Bad S02E05
              series_name: Breaking Bad
              series_season: 2
              series_episode: 5
              tmdb_id: 1396
          accept_all: yes
          list_add:
            - floppy_list: *to_download
        add_episode_show_to_list:
          mock:
            - title: Breaking Bad S02E05
              series_name: Breaking Bad
              series_season: 2
              series_episode: 5
              tmdb_id: 1396
          accept_all: yes
          list_add:
            - floppy_list:
                <<: *to_download
                type: shows
        add_to_collection:
          mock:
            - {{title: 'The.Matrix.1999.1080p.BluRay.x264-FlexGet', tmdb_id: 603}}
            - title: Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet
              series_name: Breaking Bad
              series_season: 2
              series_episode: 5
              tvdb_id: 81189
            - {{title: 'Breaking Bad', series_name: 'Breaking Bad', tmdb_id: 1396}}
          accept_all: yes
          list_add:
            - floppy_list: *collection
        add_by_name:
          mock:
            - {{title: 'The Matrix (1999)', movie_name: 'The Matrix', movie_year: 1999}}
            - title: Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet
              series_name: Breaking Bad (2008)
              series_season: 2
              series_episode: 5
          accept_all: yes
          list_add:
            - floppy_list: *collection
        remove_from_list:
          mock:
            - {{title: 'The Matrix (1999)', movie_name: 'The Matrix', tmdb_id: 603}}
          accept_all: yes
          list_remove:
            - floppy_list: *to_download
        match_collection:
          mock:
            - title: Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet
              series_name: Breaking Bad
              series_season: 2
              series_episode: 5
            - title: Breaking.Bad.S02E06.720p.HDTV.x264-FlexGet
              series_name: Breaking Bad
              series_season: 2
              series_episode: 6
            - {{title: 'The.Matrix.1999.1080p.BluRay.x264-FlexGet', tmdb_id: 603}}
          list_match:
            from:
              - floppy_list: *collection
            single_match: no
        match_list:
          mock:
            - title: Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet
              series_name: Breaking Bad
              series_season: 2
              series_episode: 5
            - {{title: 'Breaking Bad 1396', movie_name: 'Breaking Bad 1396', tmdb_id: 1396}}
          list_match:
            from:
              - floppy_list: *to_download
            single_match: no
    """

    def test_read_list(self, execute_task, floppy):
        floppy.lists[1][1].extend([
            floppy_item('movie', 603, 'The Matrix', year=1999, ids={'imdb': 'tt0133093'}),
            floppy_item('tv', 1396, 'Breaking Bad', year=2008, ids={'tvdb': '81189'}),
            floppy_item('season', 1396, 'Breaking Bad', season=2),
            floppy_item('book', 5, 'Dune'),
        ])

        task = execute_task('read_list')

        assert len(task.entries) == 3
        movie = task.find_entry(title='The Matrix (1999)')
        assert movie['movie_name'] == 'The Matrix'
        assert movie['movie_year'] == 1999
        assert movie['tmdb_id'] == 603
        assert movie['imdb_id'] == 'tt0133093'
        assert movie['url'] == f'{BASE_URL}/details/tmdb/movie/603/slug'
        show = task.find_entry(title='Breaking Bad (2008)')
        assert show['series_name'] == 'Breaking Bad (2008)'
        assert show['tmdb_id'] == 1396
        assert show['tvdb_id'] == 81189
        season = task.find_entry(title='Breaking Bad (2008) S02')
        assert season['series_season'] == 2
        assert season['tmdb_id'] == 1396

    def test_read_collection(self, execute_task, floppy):
        floppy.collection.extend([
            floppy_item('movie', 603, 'The Matrix'),
            floppy_item('episode', 1396, 'Breaking Bad', season=2, episode=5),
        ])

        task = execute_task('read_collection')

        assert task.find_entry(title='The Matrix', tmdb_id=603)
        episode = task.find_entry(title='Breaking Bad S02E05')
        assert episode['series_name'] == 'Breaking Bad'
        assert episode['series_id'] == 'S02E05'
        assert (episode['series_season'], episode['series_episode']) == (2, 5)

    def test_unknown_list(self, floppy):
        config = {'base_url': BASE_URL, 'api_key': API_KEY, 'list': 'nope'}
        with pytest.raises(Exception, match='does not appear to exist'):
            list(FloppySet(config))

    def test_add_to_list(self, execute_task, floppy):
        execute_task('add_to_list')

        assert floppy.calls == [
            ('put', 'media/movie/tmdb/603/lists/1', None),
            # tvdb id resolved to a tmdb id
            ('put', 'media/tv/tmdb/1396/lists/1', None),
        ]

    def test_episode_not_added_to_list(self, execute_task, floppy):
        execute_task('add_episode_to_list')
        assert floppy.calls == []

    def test_episode_adds_show_when_type_is_shows(self, execute_task, floppy):
        execute_task('add_episode_show_to_list')
        assert floppy.calls == [('put', 'media/tv/tmdb/1396/lists/1', None)]

    def test_add_to_collection(self, execute_task, floppy):
        execute_task('add_to_collection')

        assert floppy.calls == [
            ('put', 'media/movie/tmdb/603/collection', {'resolution': '1080p'}),
            ('put', 'media/tv/tmdb/1396/2/episodes/5/collection', {'resolution': '720p'}),
            # the bare show is skipped: floppy collects shows per episode
        ]

    def test_add_without_ids_searches_by_name(self, execute_task, floppy):
        execute_task('add_by_name')

        assert floppy.tmdb_calls == [
            ('search/movie', {'query': 'The Matrix', 'year': 1999}),
            ('search/tv', {'query': 'Breaking Bad', 'first_air_date_year': 2008}),
        ]
        assert floppy.calls == [
            ('put', 'media/movie/tmdb/603/collection', {}),
            # the result named exactly like the series wins over the first result
            ('put', 'media/tv/tmdb/1396/2/episodes/5/collection', {'resolution': '720p'}),
        ]

    def test_remove_from_list(self, execute_task, floppy):
        execute_task('remove_from_list')
        assert floppy.calls == [('delete', 'media/movie/tmdb/603/lists/1', None)]

    def test_match_collection(self, execute_task, floppy):
        floppy.collection.extend([
            floppy_item('movie', 603, 'The Matrix'),
            floppy_item('episode', 1396, 'Breaking Bad', season=2, episode=5),
        ])

        task = execute_task('match_collection')

        assert sorted(entry['title'] for entry in task.accepted) == [
            'Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet',
            'The.Matrix.1999.1080p.BluRay.x264-FlexGet',
        ]

    def test_match_show_in_list(self, execute_task, floppy):
        floppy.lists[1][1].append(floppy_item('tv', 1396, 'Breaking Bad', year=2008))

        task = execute_task('match_list')

        # Every episode of a listed show matches, a movie with the same tmdb id does not
        assert [entry['title'] for entry in task.accepted] == [
            'Breaking.Bad.S02E05.720p.HDTV.x264-FlexGet'
        ]


@register_lazy_lookup('floppy_list_test_tmdb_id')
def lazy_tmdb_id(entry):
    entry['tmdb_id'] = 603


def floppy_set(list_name='To Download', **config):
    return FloppySet({'base_url': BASE_URL, 'api_key': API_KEY, 'list': list_name, **config})


def episode_entry(season=2, episode=5, series_name='Breaking Bad', **fields):
    return Entry(
        title=f'{series_name} episode',
        url='mock://episode',
        series_name=series_name,
        series_season=season,
        series_episode=episode,
        **fields,
    )


class TestFloppySet:
    config = 'tasks: {}'

    def test_set_interface(self, floppy):
        floppy.lists[1][1].append(floppy_item('movie', 603, 'The Matrix', year=1999))
        matrix = Entry(title='The Matrix', url='mock://matrix', tmdb_id=603)
        inception = Entry(title='Inception', url='mock://inception', tmdb_id=27205)
        the_list = floppy_set()

        assert the_list.online
        assert the_list.immutable is None
        assert len(the_list) == 1
        assert matrix in the_list
        assert inception not in the_list
        assert the_list.get(matrix)['title'] == 'The Matrix (1999)'

        the_list.add(inception)
        the_list.discard(matrix)
        assert floppy.calls == [
            ('put', 'media/movie/tmdb/27205/lists/1', None),
            ('delete', 'media/movie/tmdb/603/lists/1', None),
        ]

    def test_clear(self, floppy):
        floppy.lists[1][1].extend([
            floppy_item('movie', 603, 'The Matrix'),
            floppy_item('tv', 1396, 'Breaking Bad'),
            floppy_item('season', 1396, 'Breaking Bad', season=2),
        ])

        floppy_set().clear()
        # An empty list has nothing to clear
        floppy_set('Empty').clear()

        assert floppy.calls == [
            ('delete', 'media/movie/tmdb/603/lists/1', None),
            ('delete', 'media/tv/tmdb/1396/lists/1', None),
            ('delete', 'media/tv/tmdb/1396/2/lists/1', None),
        ]

    def test_items_are_cached_until_the_list_changes(self, floppy):
        floppy.lists[1][1].append(floppy_item('movie', 603, 'The Matrix'))
        the_list = floppy_set()
        assert len(the_list) == 1

        floppy.lists[1][1].append(floppy_item('movie', 27205, 'Inception'))
        assert len(the_list) == 1

        the_list.add(Entry(title='Dune', url='mock://dune', tmdb_id=438631))
        assert len(the_list) == 2

    @pytest.mark.parametrize(
        ('list_type', 'titles'),
        [
            ('movies', ['The Matrix']),
            ('shows', ['Breaking Bad']),
            ('seasons', ['Breaking Bad S02']),
            ('episodes', ['Breaking Bad S02E05']),
        ],
    )
    def test_type_limits_items(self, floppy, list_type, titles):
        floppy.lists[1][1].extend([
            floppy_item('movie', 603, 'The Matrix'),
            floppy_item('tv', 1396, 'Breaking Bad'),
            floppy_item('season', 1396, 'Breaking Bad', season=2),
            floppy_item('episode', 1396, 'Breaking Bad', season=2, episode=5),
        ])

        assert [entry['title'] for entry in floppy_set(type=list_type)] == titles

    def test_strip_dates(self, floppy):
        floppy.lists[1][1].extend([
            floppy_item('movie', 603, 'The Matrix', year=1999),
            floppy_item('tv', 1396, 'Breaking Bad', year=2008),
        ])

        entries = list(floppy_set(strip_dates=True))

        assert [entry['title'] for entry in entries] == ['The Matrix', 'Breaking Bad']
        assert entries[0]['movie_year'] == 1999

    def test_items_without_usable_data(self, floppy):
        anime = floppy_item('anime', 2001, 'Cowboy Bebop', ids={'imdb': None})
        anime.update(source='mal', url=None)
        anime_season = floppy_item('season', 2001, 'Cowboy Bebop', season=1)
        anime_season['source'] = 'mal'
        floppy.lists[1][1].extend([floppy_item('movie', 1, ''), anime, anime_season])

        entries = [dict(entry) for entry in floppy_set()]

        # The untitled movie is skipped, and ids that are not tmdb ids are not passed off as such
        assert entries == [
            {
                'title': 'Cowboy Bebop',
                'original_title': 'Cowboy Bebop',
                'series_name': 'Cowboy Bebop',
                'url': f'{BASE_URL}/details/mal/anime/2001',
                'original_url': f'{BASE_URL}/details/mal/anime/2001',
            },
            {
                'title': 'Cowboy Bebop S01',
                'original_title': 'Cowboy Bebop S01',
                'series_name': 'Cowboy Bebop',
                'series_season': 1,
                'url': f'{BASE_URL}/details/tmdb/season/2001/slug#S01',
                'original_url': f'{BASE_URL}/details/tmdb/season/2001/slug#S01',
            },
        ]

    @pytest.mark.parametrize(
        ('path', 'response', 'message'),
        [
            ('lists/1/items', FakeResponse(404), 'does not appear to exist'),
            ('lists', FakeResponse(401), 'Authentication error'),
            ('lists/1/items', FakeResponse(403), 'Authentication error'),
            ('lists/1/items', FakeResponse(500, 'boom'), 'Error getting data from floppy: boom'),
            ('lists/1/items', FakeResponse(200, ValueError), 'Error getting list from floppy'),
            ('lists/1/items', RequestException('down'), 'Could not retrieve list from floppy'),
        ],
    )
    def test_read_errors(self, floppy, path, response, message):
        floppy.overrides[path] = response
        with pytest.raises(PluginError, match=message):
            list(floppy_set())

    def test_matching(self, floppy):
        floppy.lists[1][1].extend([
            floppy_item('movie', 603, 'The Matrix', year=1999),
            floppy_item('tv', 1396, 'Breaking Bad', year=2008, ids={'tvdb': '81189'}),
            floppy_item('season', 1399, 'Game of Thrones', season=1),
        ])
        the_list = floppy_set()

        def movie(**fields):
            return Entry(title='a movie', url='mock://movie', **fields)

        def show(name, **fields):
            return Entry(title=name, url='mock://show', series_name=name, **fields)

        assert movie(movie_name='The Matrix', movie_year=1999) in the_list
        assert movie(movie_name='The Matrix', movie_year=2021) not in the_list
        assert movie() not in the_list
        # By id, whatever the name
        assert show('BrBa', tvdb_id=81189) in the_list
        # By name, the year only has to agree when both sides know it
        assert show('breaking bad') in the_list
        assert show('Breaking Bad (2008)') in the_list
        assert show('Breaking Bad (2025)') not in the_list
        # A season in the list matches its own episodes only
        thrones = {'series_name': 'Game of Thrones'}
        assert the_list.get(episode_entry(season=1, episode=3, **thrones))['series_season'] == 1
        assert episode_entry(season=1, episode=3, **thrones) in the_list
        assert episode_entry(season=2, episode=3, **thrones) not in the_list
        assert show('Game of Thrones') not in the_list
        # An item that is not a show can not be matched as one
        assert not the_list.show_match(show('The Matrix'), movie(movie_name='The Matrix'))


class TestFloppySubmit:
    config = 'tasks: {}'

    @pytest.mark.parametrize(
        ('list_name', 'list_type', 'entry', 'call'),
        [
            ('To Download', 'auto', episode_entry(episode=None), 'media/tv/tmdb/1396/2/lists/1'),
            ('To Download', 'seasons', episode_entry(), 'media/tv/tmdb/1396/2/lists/1'),
            ('To Download', 'seasons', episode_entry(season=None, episode=None), None),
            ('To Download', 'episodes', episode_entry(episode=None), None),
            ('To Download', 'shows', Entry(title='The Matrix', url='mock://', tmdb_id=603), None),
            ('To Download', 'movies', episode_entry(), 'media/movie/tmdb/1396/lists/1'),
            ('collection', 'auto', episode_entry(episode=None), None),
        ],
    )
    def test_what_is_submitted(self, floppy, list_name, list_type, entry, call):
        entry['tmdb_id'] = entry.get('tmdb_id') or 1396

        floppy_set(list_name, type=list_type).add(entry)

        assert [path for _, path, _ in floppy.calls] == ([call] if call else [])

    def test_movie_tmdb_id_from_lazy_lookup(self, floppy):
        entry = Entry(title='The Matrix', url='mock://matrix')
        entry.add_lazy_fields(lazy_tmdb_id, ['tmdb_id'])

        floppy_set().add(entry)

        assert floppy.calls == [('put', 'media/movie/tmdb/603/lists/1', None)]
        assert floppy.tmdb_calls == []

    def test_tmdb_lookups_are_cached(self, floppy):
        by_tvdb = [episode_entry(episode=number, tvdb_id=81189) for number in (1, 2)]
        by_name = [episode_entry(episode=number) for number in (3, 4)]

        floppy_set('collection').__ior__(by_tvdb + by_name)

        assert len(floppy.calls) == 4
        assert [endpoint for endpoint, _ in floppy.tmdb_calls] == ['find/81189', 'search/tv']

    def test_falls_back_when_an_id_is_unknown_to_tmdb(self, floppy):
        floppy.tmdb_overrides['find/1'] = {'tv_results': []}
        floppy.tmdb_overrides['find/tt0903747'] = RequestException('down')

        floppy_set().add(
            Entry(
                title='Breaking Bad',
                url='mock://show',
                series_name='Breaking Bad',
                tvdb_id=1,
                imdb_id='tt0903747',
            )
        )

        assert [endpoint for endpoint, _ in floppy.tmdb_calls] == [
            'find/1',
            'find/tt0903747',
            'search/tv',
        ]
        assert floppy.calls == [('put', 'media/tv/tmdb/1396/lists/1', None)]

    @pytest.mark.parametrize(
        ('entry', 'search'),
        [
            # Nothing to search for
            (Entry(title='Unknown', url='mock://unknown'), None),
            (Entry(title='Dune', url='mock://dune', movie_name='Dune'), {'results': []}),
            (Entry(title='Dune', url='mock://dune', movie_name='Dune'), RequestException('down')),
        ],
    )
    def test_not_submitted_without_tmdb_id(self, floppy, entry, search):
        floppy.tmdb_overrides['search/movie'] = search

        floppy_set().add(entry)

        assert floppy.calls == []
        assert len(floppy.tmdb_calls) == (0 if search is None else 1)

    @pytest.mark.parametrize('status', [409, 404, 500])
    def test_rejected_submit_does_not_stop_the_rest(self, floppy, status):
        floppy.lists[1][1].append(floppy_item('movie', 603, 'The Matrix'))
        the_list = floppy_set()
        assert len(the_list) == 1
        floppy.submit_response = FakeResponse(status, 'nope')
        floppy.lists[1][1].append(floppy_item('movie', 27205, 'Inception'))

        the_list |= [
            Entry(title='The Matrix', url='mock://matrix', tmdb_id=603),
            Entry(title='Inception', url='mock://inception', tmdb_id=27205),
        ]

        assert len(floppy.calls) == 2
        # Nothing changed, so the items are not fetched again
        assert len(the_list) == 1

    @pytest.mark.parametrize('failure', [FakeResponse(401), FakeResponse(403), 'exception'])
    def test_failed_submit_stops(self, floppy, failure):
        if failure == 'exception':
            floppy.overrides['media/movie/tmdb/603/lists/1'] = RequestException('down')
        else:
            floppy.submit_response = failure

        floppy_set().__ior__([
            Entry(title='The Matrix', url='mock://matrix', tmdb_id=603),
            Entry(title='Inception', url='mock://inception', tmdb_id=27205),
        ])

        assert len(floppy.calls) == (0 if failure == 'exception' else 1)
