import re

import pytest

from flexget.components.floppy import floppy_list
from flexget.components.floppy.floppy_list import FloppySet

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
        return self._data


class FakeFloppy:
    """Answers the floppy endpoints the plugin uses, and records what was submitted."""

    page_size = 2

    def __init__(self):
        self.lists = {1: ('To Download', []), 2: ('Empty', [])}
        self.collection = []
        self.calls = []
        self.tmdb_calls = []

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
