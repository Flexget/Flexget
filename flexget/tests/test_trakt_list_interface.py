import time

import pytest

from flexget.components.trakt.db import TraktUserAuth
from flexget.components.trakt.trakt_list import TraktSet
from flexget.entry import Entry
from flexget.manager import Session


@pytest.mark.online
class TestTraktList:
    """
    Credentials for test account are:
       username: flexget_list_test
       password: flexget
    """

    config = """
      tasks:
        test_list:
          trakt_list:
            account: 'flexget_list_test'
            list: watchlist
            type: episodes
            strip_dates: yes
        test_add_episode_auto:
          mock:
            - {title: 'Stranger Things S01E05 720p HDTV'}
            - {title: 'Stranger Things S01E06 720p HDTV'}
          series:
            - Stranger Things:
                begin: S01E05
          list_add:
            - trakt_list:
                account: 'flexget_list_test'
                list: watchlist
                strip_dates: yes
    """

    trakt_config = {'account': 'flexget_list_test', 'list': 'watchlist', 'type': 'shows'}

    @pytest.fixture(autouse=True)
    def db_auth(self, manager):
        kwargs = {
            'account': 'flexget_list_test',
            'access_token': 'c78844ac92c43cf81662d6a132d9412220023c5c962e1a80e519472e502e45c9',
            'refresh_token': 'c33d487d3c27e33896a10f0edda08f14040ee27ee195f18442dd72555f9a9b9f',
            'created': 1546067709,
            'expires': 7776000,
        }

        # Creates the trakt token in db
        with Session() as session:
            auth = TraktUserAuth(**kwargs)
            session.add(auth)

    def test_get_list(self):
        config = {'account': 'flexget_list_test', 'list': 'testlist', 'type': 'auto'}
        trakt_set = TraktSet(config)
        entries = sorted([dict(e) for e in trakt_set], key=lambda x: sorted(x.keys()))

        assert entries == sorted(
            [
                {
                    'trakt_show_slug': 'castle',
                    'original_url': 'https://trakt.tv/shows/castle/seasons/8/episodes/15',
                    'url': 'https://trakt.tv/shows/castle/seasons/8/episodes/15',
                    'series_season': 8,
                    'tvdb_id': 83462,
                    'series_name': 'Castle (2009)',
                    'imdb_id': 'tt1219024',
                    'series_id': 'S08E15',
                    'series_episode': 15,
                    'trakt_episode_id': 2125119,
                    'trakt_series_name': 'Castle',
                    'trakt_series_year': 2009,
                    'title': 'Castle (2009) S08E15 Fidelis Ad Mortem',
                    'original_title': 'Castle (2009) S08E15 Fidelis Ad Mortem',
                    'trakt_show_id': 1410,
                    'trakt_ep_name': 'Fidelis Ad Mortem',
                    'tvrage_id': 19267,
                },
                {
                    'movie_name': 'Deadpool',
                    'original_url': 'https://trakt.tv/movies/deadpool-2016',
                    'tmdb_id': 293660,
                    'title': 'Deadpool (2016)',
                    'original_title': 'Deadpool (2016)',
                    'url': 'https://trakt.tv/movies/deadpool-2016',
                    'trakt_movie_id': 190430,
                    'trakt_movie_name': 'Deadpool',
                    'imdb_id': 'tt1431045',
                    'movie_year': 2016,
                    'trakt_movie_slug': 'deadpool-2016',
                    'trakt_movie_year': 2016,
                },
                {
                    'trakt_show_slug': 'the-walking-dead',
                    'tmdb_id': 1402,
                    'title': 'The Walking Dead (2010)',
                    'original_title': 'The Walking Dead (2010)',
                    'url': 'https://trakt.tv/shows/the-walking-dead',
                    'original_url': 'https://trakt.tv/shows/the-walking-dead',
                    'series_name': 'The Walking Dead (2010)',
                    'trakt_show_id': 1393,
                    'tvdb_id': 153021,
                    'imdb_id': 'tt1520211',
                    'trakt_series_name': 'The Walking Dead',
                    'trakt_series_year': 2010,
                    'tvrage_id': 25056,
                },
            ],
            key=lambda x: sorted(x.keys()),
        )

    def test_strip_dates(self):
        config = {
            'account': 'flexget_list_test',
            'list': 'testlist',
            'strip_dates': True,
            'type': 'auto',
        }
        trakt_set = TraktSet(config)
        titles = [e['title'] for e in trakt_set]
        assert set(titles) == {'The Walking Dead', 'Deadpool', 'Castle S08E15 Fidelis Ad Mortem'}

    def test_trakt_add(self):
        # Initialize trakt set
        trakt_set = TraktSet(self.trakt_config)
        trakt_set.clear()

        entry = Entry(title='White collar', series_name='White Collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        time.sleep(5)
        assert entry in trakt_set

    def test_trakt_add_episode(self):
        episode_config = self.trakt_config.copy()
        episode_config['type'] = 'episodes'
        trakt_set = TraktSet(episode_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(
            **{
                'trakt_show_slug': 'game-of-thrones',
                'original_url': 'https://trakt.tv/shows/game-of-thrones/seasons/4/episodes/5',
                'url': 'https://trakt.tv/shows/game-of-thrones/seasons/4/episodes/5',
                'series_season': 4,
                'tvdb_id': 121361,
                'series_name': 'Game of Thrones (2011)',
                'imdb_id': 'tt0944947',
                'series_id': 'S04E05',
                'series_episode': 5,
                'trakt_episode_id': 73674,
                'title': 'Game of Thrones (2011) S04E05 First of His Name',
                'trakt_show_id': 1390,
                'trakt_ep_name': 'First of His Name',
                'tvrage_id': 24493,
            }
        )

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set

    def test_trakt_add_episode_simple(self):
        episode_config = self.trakt_config.copy()
        episode_config['type'] = 'episodes'
        trakt_set = TraktSet(episode_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(
            **{
                'series_name': 'Game of Thrones (2011)',
                'series_id': 'S04E05',
                'series_episode': 5,
                'series_season': 4,
                'title': 'Game of Thrones (2011) S04E05 First of His Name',
            }
        )

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set

    def test_trakt_add_episode_task(self, execute_task):
        episode_config = self.trakt_config.copy()
        episode_config['type'] = 'episodes'
        # Initialize trakt set
        trakt_set = TraktSet(episode_config)
        trakt_set.clear()

        execute_task('test_add_episode_auto')

        task = execute_task('test_list')
        assert len(task.entries) == 2
        assert task.entries[0]['series_name'] == 'Stranger Things'
        assert task.entries[1]['series_name'] == 'Stranger Things'
        for series_id in ['S01E05', 'S01E06']:
            entry1 = task.entries[0]
            entry2 = task.entries[1]

            assert series_id in [entry1['series_id'], entry2['series_id']]

    def test_trakt_remove(self):
        trakt_set = TraktSet(self.trakt_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(title='White collar', series_name='White Collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        time.sleep(5)
        assert entry in trakt_set

        trakt_set.remove(entry)
        time.sleep(5)
        assert entry not in trakt_set

    def test_trakt_pagination(self):
        config = {'account': 'flexget_list_test', 'list': 'watched', 'type': 'movies'}
        trakt_set = TraktSet(config)
        assert len(trakt_set) == 25
