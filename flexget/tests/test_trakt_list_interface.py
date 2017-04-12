from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import time

import pytest

from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.internal.api_trakt import TraktUserAuth
from flexget.plugins.list.trakt_list import TraktSet


@pytest.mark.online
class TestTraktList(object):
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

    trakt_config = {'account': 'flexget_list_test',
                    'list': 'watchlist',
                    'type': 'shows'}

    @pytest.fixture(autouse=True)
    def db_auth(self, manager):
        kwargs = {
            'account': 'flexget_list_test',
            'access_token': '336e1b7bb963b63f3cda4500a31aaa06de5fc22201795c4b89e239211d418f22',
            'refresh_token': 'f07c967d834673f5e61cba0942f177fbf839528241db9cb6dfb5a51dd267692f',
            'created': 1481976079,
            'expires': 7776000
        }

        # Creates the trakt token in db
        with Session() as session:
            auth = TraktUserAuth(**kwargs)
            session.add(auth)

    def test_get_list(self):
        config = {'account': 'flexget_list_test', 'list': 'testlist', 'type': 'auto'}
        trakt_set = TraktSet(config)
        entries = sorted([dict(e) for e in trakt_set], key=lambda x: sorted(x.keys()))

        assert entries == sorted([
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
                'trakt_show_id': 1410,
                'trakt_ep_name': 'Fidelis Ad Mortem',
                'tvrage_id': 19267
            },
            {
                'movie_name': 'Deadpool',
                'original_url': 'https://trakt.tv/movies/deadpool-2016',
                'tmdb_id': 293660,
                'title': 'Deadpool (2016)',
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
                'url': 'https://trakt.tv/shows/the-walking-dead',
                'original_url': 'https://trakt.tv/shows/the-walking-dead',
                'series_name': 'The Walking Dead (2010)',
                'trakt_show_id': 1393,
                'tvdb_id': 153021,
                'imdb_id': 'tt1520211',
                'trakt_series_name': 'The Walking Dead',
                'trakt_series_year': 2010,
                'tvrage_id': 25056
            }
        ], key=lambda x: sorted(x.keys()))

    def test_strip_dates(self):
        config = {'account': 'flexget_list_test', 'list': 'testlist', 'strip_dates': True, 'type': 'auto'}
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

        entry = Entry(**{u'trakt_show_slug': u'game-of-thrones',
                         u'original_url': u'https://trakt.tv/shows/game-of-thrones/seasons/4/episodes/5',
                         u'url': u'https://trakt.tv/shows/game-of-thrones/seasons/4/episodes/5', u'series_season': 4,
                         u'tvdb_id': 121361, u'series_name': u'Game of Thrones (2011)', u'imdb_id': u'tt0944947',
                         u'series_id': u'S04E05', u'series_episode': 5, u'trakt_episode_id': 73674,
                         u'title': u'Game of Thrones (2011) S04E05 First of His Name', u'trakt_show_id': 1390,
                         u'trakt_ep_name': u'First of His Name', u'tvrage_id': 24493})

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set

    def test_trakt_add_episode_simple(self):
        episode_config = self.trakt_config.copy()
        episode_config['type'] = 'episodes'
        trakt_set = TraktSet(episode_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(**{u'series_name': u'Game of Thrones (2011)', u'series_id': u'S04E05', u'series_episode': 5,
                         u'series_season': 4, u'title': u'Game of Thrones (2011) S04E05 First of His Name'})

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
        assert task.entries[0]['series_name'] == 'Stranger Things (2016)'
        assert task.entries[1]['series_name'] == 'Stranger Things (2016)'
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
