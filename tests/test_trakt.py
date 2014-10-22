from __future__ import unicode_literals, division, absolute_import

import httmock

from flexget.plugins.api_trakt import ApiTrakt
from tests import FlexGetBase, use_vcr


lookup_series = ApiTrakt.lookup_series
lookup_episode = ApiTrakt.lookup_episode


class TestTraktLookup(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            trakt_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{trakt_series_tvdb_id}}{{trakt_ep_name}}"
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House
              - Doctor Who 2005
          test_unknown_series:
            mock:
              - {title: 'Aoeu.Htns.S01E01.htvd'}
            series:
              - Aoeu Htns
          test_date:
            mock:
              - title: the daily show 2012-6-6
            series:
              - the daily show (with jon stewart)
          test_absolute:
            mock:
              - title: naruto 128
            series:
              - naruto

    """

    @use_vcr
    def test_lookup(self):
        """trakt: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_ep_name'] == 'Paternity', \
            '%s trakt_ep_name should be Paternity' % entry['title']
        assert entry['trakt_series_status'] == 'Ended', \
            'runtime for %s is %s, should be Ended' % (entry['title'], entry['trakt_series_status'])
        assert entry['afield'] == '73255Paternity', 'afield was not set correctly'
        assert self.task.find_entry(trakt_ep_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'

    @use_vcr
    def test_unknown_series(self):
        # Test an unknown series does not cause any exceptions
        self.execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = self.task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    @use_vcr
    def test_date(self):
        self.execute_task('test_date')
        entry = self.task.find_entry(title='the daily show 2012-6-6')
        assert entry.get('tvdb_id') is None, 'should not have populated trakt data'

    @use_vcr
    def test_absolute(self):
        self.execute_task('test_absolute')
        entry = self.task.find_entry(title='naruto 128')
        assert entry.get('tvdb_id') is None, 'should not have populated trakt data'


class TestTraktList(FlexGetBase):
    __yaml__ = """
        tasks:
          test_trakt_movies:
            trakt_list:
              api_key: 1234
              username: testuser
              movies: watchlist
    """

    def test_trakt_movies(self):

        @httmock.all_requests
        def movie_request(url, request):
            assert url.path.endswith('watchlist/movies.json/1234/testuser')
            return (
                b'[{"title":"12 Angry Men","year":1957,"released":-401731200,"url":"http://trakt.tv/movie/12-angry-men-'
                b'1957","trailer":"http://youtube.com/watch?v=OvebOqneLIU","runtime":96,"tagline":"Life is in their han'
                b'ds. Death is on their minds.","overview":"The defense and the prosecution have rested and the jury is'
                b' filing into the jury room to decide if a young Spanish-American is guilty or innocent of murdering h'
                b'is father. What begins as an open and shut case soon becomes a mini-drama of each of the jurors\' pre'
                b'judices and preconceptions about the trial, the accused, and each other.","certification":"PG","imdb_'
                b'id":"tt0050083","tmdb_id":"389","inserted":1374718966,"images":{"poster":"http://slurm.trakt.us/image'
                b's/posters_movies/484.2.jpg","fanart":"http://slurm.trakt.us/images/fanart_movies/484.2.jpg"},"genres"'
                b':["Drama"],"ratings":{"percentage":89,"votes":1533,"loved":1514,"hated":19}}]')

        with httmock.HTTMock(movie_request):
            self.execute_task('test_trakt_movies')
            assert len(self.task.entries) == 1
            entry = self.task.entries[0]
            assert entry['title'] == '12 Angry Men'
            assert entry['movie_name'] == '12 Angry Men'
            assert entry['movie_year'] == 1957
            assert entry['imdb_id'] == 'tt0050083'
