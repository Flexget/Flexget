from __future__ import annotations

from unittest import mock

import jsonschema
import pytest

from flexget import plugin
from flexget.components.managed_lists.lists.scrob_list import (
    ScrobApiError,
    ScrobAPIWrapper,
    ScrobSet,
)
from flexget.entry import Entry


def _mock_media(tmdb_id, media_type, title, release_date=None, season_number=None):
    return {
        'id': tmdb_id * 10,
        'tmdb_id': tmdb_id,
        'type': media_type,
        'title': title,
        'poster_path': None,
        'backdrop_path': None,
        'release_date': release_date,
        'tmdb_rating': 7.5,
        'season_number': season_number,
        'episode_number': None,
    }


def _mock_item(item_id, media):
    return {
        'id': item_id,
        'list_id': 1,
        'added_at': '2026-01-01T00:00:00',
        'sort_order': 0,
        'notes': None,
        'media': media,
    }


class MockedScrobBackend:
    def __init__(self):
        self.next_item_id = 100
        self.lists = {
            1: {
                'id': 1,
                'name': 'Watchlist',
                'items': [
                    _mock_item(1, _mock_media(603692, 'movie', 'Deadpool', release_date='2016-02-12')),  # movie
                    _mock_item(2, _mock_media(1399, 'series', 'Game of Thrones', release_date='2011-04-17')),  # series
                    # season
                    _mock_item(
                        3,
                        _mock_media(
                            1399,
                            'series',
                            'Game of Thrones',
                            release_date='2011-04-17',
                            season_number=1,
                        ),
                    ),
                    _mock_item(4, _mock_media(1399, 'episode', 'Winter Is Coming')),  # episode
                    _mock_item(5, _mock_media(9999999, 'movie', 'No Imdb Movie', release_date=None)),  # broken movie
                ],
            }
        }
        self.movie_details = {
            603692: {'tmdb_id': 603692, 'imdb_id': 'tt1431045'},
        }
        self.posts = []
        self.deletes = []

    def __call__(self, method, path, **kwargs):
        if method == 'get' and path.startswith('lists/') and '/' not in path[len('lists/'):]:
            list_id = int(path.split('/')[1])
            lst = self.lists.get(list_id)
            if lst is None:
                raise ScrobApiError('List not found', status_code=404)
            return dict(lst)
        if method == 'get' and path.startswith('media/movie/'):
            tmdb_id = int(path.rsplit('/', 1)[-1])
            detail = self.movie_details.get(tmdb_id)
            if not detail:
                raise ScrobApiError('TMDB Media not found', status_code=404)
            return detail
        if method == 'post' and path.endswith('/items'):
            list_id = int(path.split('/')[1])
            body = kwargs.get('json') or {}
            self.posts.append((list_id, body))
            existing = [
                i
                for i in self.lists[list_id]['items']
                if i['media']['tmdb_id'] == body['tmdb_id']
                and i['media']['type'] == body['media_type']
            ]
            if existing:
                raise ScrobApiError('Already in list', status_code=409)
            self.next_item_id += 1
            item = _mock_item(
                self.next_item_id, _mock_media(body['tmdb_id'], body['media_type'], 'Added Title')
            )
            self.lists[list_id]['items'].append(item)
            return item
        if method == 'delete' and '/items/' in path:
            list_id = int(path.split('/')[1])
            item_id = int(path.rsplit('/', 1)[-1])
            self.deletes.append((list_id, item_id))
            before = len(self.lists[list_id]['items'])
            self.lists[list_id]['items'] = [
                i for i in self.lists[list_id]['items'] if i['id'] != item_id
            ]
            if len(self.lists[list_id]['items']) == before:
                raise ScrobApiError('Item not found', status_code=404)
            return {'message': 'Item removed'}
        raise AssertionError(f'Unexpected request: {method} {path}')


@pytest.fixture
def backend():
    return MockedScrobBackend()


@pytest.fixture(autouse=True)
def patched_request(backend):
    with mock.patch.object(ScrobAPIWrapper, '_request', side_effect=backend):
        yield backend


def _config(list_id=1, strip_year=False):
    return {
        'base_url': 'http://scrob.test',
        'api_key': 'testkey',
        'list_id': list_id,
        'strip_year': strip_year
    }


class TestScrobSetRead:
    def test_filters_seasons_and_episodes(self, backend):
        scrob_set = ScrobSet(_config())
        titles = {e['title'] for e in scrob_set}
        assert titles == {'Deadpool (2016)', 'Game of Thrones (2011)', 'No Imdb Movie'}

    def test_len_and_iter(self, backend):
        scrob_set = ScrobSet(_config())
        assert len(scrob_set) == 3
        assert len(list(scrob_set)) == 3

    def test_movie_fields(self, backend):
        scrob_set = ScrobSet(_config())
        entry = next(e for e in scrob_set if e['tmdb_id'] == 603692)
        assert entry['movie_name'] == 'Deadpool'
        assert entry['movie_year'] == 2016
        assert isinstance(entry['movie_year'], int)
        assert entry['imdb_id'] == 'tt1431045'
        assert entry['url'] == 'https://www.themoviedb.org/movie/603692'
        assert entry['scrob_media_type'] == 'movie'

    def test_series_fields(self, backend):
        scrob_set = ScrobSet(_config())
        entry = next(e for e in scrob_set if e['tmdb_id'] == 1399)
        assert entry['series_name'] == 'Game of Thrones'
        assert entry['series_year'] == 2011
        assert isinstance(entry['series_year'], int)
        assert entry['url'] == 'https://www.themoviedb.org/tv/1399'
        assert 'imdb_id' not in entry

    def test_broken_movie(self, backend):
        scrob_set = ScrobSet(_config())
        entry = next(e for e in scrob_set if e['tmdb_id'] == 9999999)
        assert entry['title'] == 'No Imdb Movie'
        assert 'movie_year' not in entry
        assert 'imdb_id' not in entry

    def test_strip_year(self, backend):
        scrob_set = ScrobSet(_config(strip_year=True))
        entry = next(e for e in scrob_set if e['tmdb_id'] == 603692)
        assert entry['title'] == 'Deadpool'
        assert entry['movie_year'] == 2016

    def test_missing_list_error(self, backend):
        scrob_set = ScrobSet(_config(list_id=999))
        with pytest.raises(plugin.PluginError):
            list(scrob_set)


class TestScrobSetMembership:
    def test_contains(self, backend):
        scrob_set = ScrobSet(_config())
        movie_entry = Entry(title='x', tmdb_id=603692)
        series_entry = Entry(title='x', series_name='Game of Thrones', tmdb_id=1399)
        wrong_type_entry = Entry(title='x', series_name='Foo', tmdb_id=603692)

        assert movie_entry in scrob_set
        assert series_entry in scrob_set
        assert wrong_type_entry not in scrob_set

    def test_entry_media_type(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='x', tmdb_id=603692, series_name='Foo')
        assert entry not in scrob_set

    def test_entry_media_type_default(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='x', tmdb_id=603692)
        assert entry in scrob_set

    def test_get(self, backend):
        scrob_set = ScrobSet(_config())
        found = scrob_set.get(Entry(title='x', tmdb_id=603692))
        assert found is not None
        assert found['tmdb_id'] == 603692
        assert scrob_set.get(Entry(title='x', tmdb_id=42)) is None


class TestScrobSetAdd:
    def test_add_new_movie(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='Inception', tmdb_id=27205)
        assert entry not in scrob_set

        scrob_set.add(entry)

        assert backend.posts == [(1, {'tmdb_id': 27205, 'media_type': 'movie'})]
        assert entry in scrob_set

    def test_add_new_series(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='Severance', series_name='Severance', tmdb_id=95396)

        scrob_set.add(entry)

        assert backend.posts == [(1, {'tmdb_id': 95396, 'media_type': 'series'})]
        assert entry in scrob_set

    def test_add_already_present_skips(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='Deadpool', tmdb_id=603692)

        scrob_set.add(entry)

        assert backend.posts == []

    def test_add_without_tmdb_id_skips(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='No Tmdb Id')

        scrob_set.add(entry)

        assert backend.posts == []


class TestScrobSetDiscard:
    def test_discard(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='Deadpool', tmdb_id=603692)
        assert entry in scrob_set

        scrob_set.discard(entry)

        assert backend.deletes == [(1, 1)]
        assert entry not in scrob_set

    def test_discard_noop(self, backend):
        scrob_set = ScrobSet(_config())
        entry = Entry(title='Not In List', tmdb_id=123456)

        scrob_set.discard(entry)

        assert backend.deletes == []


class TestScrobListSchema:
    def test_invalid_property(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {'api_key': 'x', 'list_name': 'Watchlist'},
                ScrobSet.schema,
            )

    def test_required_properties(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({'api_key': 'x'}, ScrobSet.schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({'list_id': 1}, ScrobSet.schema)
        jsonschema.validate({'api_key': 'x', 'list_id': 1}, ScrobSet.schema)

    def test_default_properties(self):
        assert ScrobSet.schema['properties']['base_url']['default'] == 'http://localhost:7330'
        assert not ScrobSet.schema['properties']['strip_year']['default']


class TestScrobListTask:
    config = """
        tasks:
          add_movie:
            mock:
              - {title: 'Inception', tmdb_id: 27205}
            accept_all: yes
            list_add:
              - scrob_list:
                  base_url: http://scrob.test
                  api_key: testkey
                  list_id: 1

          remove_movie:
            mock:
              - {title: 'Deadpool', tmdb_id: 603692}
            accept_all: yes
            list_remove:
              - scrob_list:
                  base_url: http://scrob.test
                  api_key: testkey
                  list_id: 1

          read_list:
            scrob_list:
              base_url: http://scrob.test
              api_key: testkey
              list_id: 1

          missing_list:
            scrob_list:
              base_url: http://scrob.test
              api_key: testkey
              list_id: 999
    """

    def test_read_list(self, execute_task, backend):
        task = execute_task('read_list')
        assert len(task.entries) == 3
        titles = {e['title'] for e in task.entries}
        assert titles == {'Deadpool (2016)', 'Game of Thrones (2011)', 'No Imdb Movie'}

    def test_list_add(self, execute_task, backend):
        execute_task('add_movie')
        assert backend.posts == [(1, {'tmdb_id': 27205, 'media_type': 'movie'})]

    def test_list_remove(self, execute_task, backend):
        execute_task('remove_movie')
        assert backend.deletes == [(1, 1)]

    def test_missing_list_aborts(self, execute_task, backend):
        execute_task('missing_list', abort=True)
