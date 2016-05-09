from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.api_trakt import TraktUserAuth
from flexget.plugins.list.trakt_list import TraktSet


@pytest.mark.online
class TestTraktList(object):
    """
    Credentials for test account are:
       username: flexget_list_test
       password: flexget
    """

    config = """
      'tasks': {}
    """

    trakt_config = {'account': 'flexget_list_test',
                    'list': 'watchlist',
                    'type': 'shows'}

    @pytest.fixture(autouse=True)
    def db_auth(self, manager):
        kwargs = {
            'account': 'flexget_list_test',
            'access_token': '60a093e80b670a254ec40b7a0d2d7535119b3bcc61859b052ae641c3009dd75b',
            'refresh_token': '006c4813fc0bd8e02219c2ce4b0295228f2ce651419adea1bfb0aded352b59d2',
            'created': 1458488839.44,
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
                'original_url': 'http://trakt.tv/shows/castle/seasons/8/episodes/15',
                'url': 'http://trakt.tv/shows/castle/seasons/8/episodes/15',
                'series_season': 8,
                'tvdb_id': 83462,
                'series_name': 'Castle (2009)',
                'imdb_id': 'tt1219024',
                'series_id': 'S08E15',
                'series_episode': 15,
                'trakt_episode_id': 2125119,
                'title': 'Castle (2009) S08E15 Fidelis Ad Mortem',
                'trakt_show_id': 1410,
                'trakt_ep_name': 'Fidelis Ad Mortem',
                'tvrage_id': 19267
            },
            {
                'movie_name': 'Deadpool',
                'original_url': 'http://trakt.tv/movie/deadpool-2016',
                'tmdb_id': 293660,
                'title': 'Deadpool (2016)',
                'url': 'http://trakt.tv/movie/deadpool-2016',
                'trakt_movie_id': 190430,
                'imdb_id': 'tt1431045',
                'movie_year': 2016,
                'trakt_movie_slug': 'deadpool-2016'
            },
            {
                'trakt_show_slug': 'the-walking-dead',
                'tmdb_id': 1402,
                'title': 'The Walking Dead (2010)',
                'url': 'http://trakt.tv/show/the-walking-dead',
                'original_url': 'http://trakt.tv/show/the-walking-dead',
                'series_name': 'The Walking Dead (2010)',
                'trakt_show_id': 1393,
                'tvdb_id': 153021,
                'imdb_id': 'tt1520211',
                'tvrage_id': 25056
            }
        ], key=lambda x: sorted(x.keys()))

    def test_strip_dates(self):
        config = {'account': 'flexget_list_test', 'list': 'testlist', 'strip_dates': True, 'type': 'auto'}
        trakt_set = TraktSet(config)
        titles = [e['title'] for e in trakt_set]
        assert set(titles) == set(('The Walking Dead', 'Deadpool', 'Castle S08E15 Fidelis Ad Mortem'))

    def test_trakt_add(self):
        trakt_set = TraktSet(self.trakt_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(title='White collar', series_name='White Collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set

    def test_trakt_remove(self):
        trakt_set = TraktSet(self.trakt_config)
        # Initialize trakt set
        trakt_set.clear()

        entry = Entry(title='White collar', series_name='White Collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set

        trakt_set.remove(entry)
        assert entry not in trakt_set

