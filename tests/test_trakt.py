from __future__ import unicode_literals, division, absolute_import

from flexget.manager import Session
from flexget.plugins.api_trakt import ApiTrakt, TraktActor, TraktMovieSearchResult, TraktShowSearchResult, TraktShow
from tests import FlexGetBase, use_vcr


lookup_series = ApiTrakt.lookup_series


class TestTraktShowLookup(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            trakt_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{tvdb_id}}{{trakt_ep_name}}"
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
          test_search_result:
            mock:
              - {title: 'Shameless.2011.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Shameless.2011.S03E02.HDTV.XViD-FlexGet'}
            series:
              - Shameless (2011)
    """

    @use_vcr
    def test_lookup_name(self):
        """trakt: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_show_id'] == 1399, \
            'Trakt_ID should be 1339 is %s for %s' % (entry['trakt_show_id'], entry['series_name'])
        assert entry['trakt_series_status'] == 'ended', 'Series Status should be "ENDED" returned %s' \
                                                        % (entry['trakt_series_status'])

    @use_vcr
    def test_lookup(self):
        """trakt: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_ep_name'] == 'Paternity', \
            '%s trakt_ep_name should be Paternity' % entry['title']
        assert entry['trakt_series_status'] == 'ended', \
            'runtime for %s is %s, should be "ended"' % (entry['title'], entry['trakt_series_status'])
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
    def test_search_results(self):
        self.execute_task('test_search_result')
        entry = self.task.entries[0]
        assert entry['trakt_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        with Session() as session:
            assert self.task.entries[1]['trakt_series_name'].lower() == 'Shameless'.lower(), 'second lookup failed'

            assert len(session.query(TraktShowSearchResult).all()) == 1, 'should have added 1 show to search result'

            assert len(session.query(TraktShow).all()) == 1, 'should only have added one show to show table'
            assert session.query(TraktShow).first().title == 'Shameless', 'should have added Shameless and' \
                                                                          'not Shameless (2011)'

    @use_vcr
    def test_date(self):
        self.execute_task('test_date')
        entry = self.task.find_entry(title='the daily show 2012-6-6')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 2211, 'should have populated trakt show data'
        # We don't support lookup by date at the moment, make sure there isn't a false positive
        if entry.get('trakt_episode_id') == 173423:
            assert False, 'We support trakt episode lookup by date now? Great! Change this test.'
        else:
            assert entry.get('trakt_episode_id') is None, 'false positive for episode match, we don\'t ' \
                                                          'support lookup by date'

    @use_vcr
    def test_absolute(self):
        self.execute_task('test_absolute')
        entry = self.task.find_entry(title='naruto 128')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 46003, 'should have populated trakt show data'
        # We don't support lookup by absolute number at the moment, make sure there isn't a false positive
        if entry.get('trakt_episode_id') == 916040:
            assert False, 'We support trakt episode lookup by absolute number now? Great! Change this test.'
        else:
            assert entry.get('trakt_episode_id') is None, 'false positive for episode match, we don\'t ' \
                                                          'support lookup by absolute number'

    @use_vcr
    def test_lookup_actors(self):
        self.execute_task('test')
        actors = ['Hugh Laurie',
                  'Jesse Spencer',
                  'Jennifer Morrison',
                  'Omar Epps',
                  'Robert Sean Leonard',
                  'Peter Jacobson',
                  'Olivia Wilde',
                  'Odette Annable',
                  'Charlyne Yi',
                  'Anne Dudek',
                  'Kal Penn',
                  'Jennifer Crystal Foley',
                  'Bobbin Bergstrom',
                  'Sela Ward']
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        trakt_actors = entry['trakt_series_actors'].values()
        trakt_actors = [trakt_actor['name'] for trakt_actor in trakt_actors]
        assert entry['series_name'] == 'House', 'series lookup failed'
        assert set(trakt_actors) == set(actors), 'looking up actors for %s failed' % entry.get('title')
        assert entry['trakt_series_actors']['297390']['name'] == 'Hugh Laurie', 'trakt id mapping failed'
        assert entry['trakt_series_actors']['297390']['imdb_id'] == 'nm0491402', 'fetching imdb id for actor failed'
        assert entry['trakt_series_actors']['297390']['tmdb_id'] == '41419', 'fetching tmdb id for actor failed'
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Hugh Laurie').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb_id == 'nm0491402', 'saving imdb_id for actors in table failed'
            assert actor.trakt_id == '297390', 'saving trakt_id for actors in table failed'
            assert actor.tmdb_id == '41419', 'saving tmdb_id for actors table failed'


class TestTraktList(FlexGetBase):
    __yaml__ = """
        tasks:
          test_trakt_movies:
            trakt_list:
              username: flexgettest
              list: watchlist
              type: movies
    """

    @use_vcr
    def test_trakt_movies(self):
        self.execute_task('test_trakt_movies')
        assert len(self.task.entries) == 1
        entry = self.task.entries[0]
        assert entry['title'] == '12 Angry Men (1957)'
        assert entry['movie_name'] == '12 Angry Men'
        assert entry['movie_year'] == 1957
        assert entry['imdb_id'] == 'tt0050083'


class TestTraktWatchedAndCollected(FlexGetBase):
    __yaml__ = """
        tasks:
          test_trakt_watched:
            metainfo_series: yes
            trakt_lookup:
                username: flexgettest
            mock:
              - title: Hawaii.Five-0.S04E13.HDTV-FlexGet
              - title: The.Flash.2014.S01E10.HDTV-FlexGet
            if:
              - trakt_watched: accept
          test_trakt_collected:
            metainfo_series: yes
            trakt_lookup:
               username: flexgettest
            mock:
              - title: Homeland.2011.S02E01.HDTV-FlexGet
              - title: The.Flash.2014.S01E10.HDTV-FlexGet
            if:
              - trakt_collected: accept
          test_trakt_watched_movie:
            trakt_lookup:
                username: flexgettest
            mock:
              - title: Inside.Out.2015.1080p.BDRip-FlexGet
              - title: The.Matrix.1999.1080p.BDRip-FlexGet
            if:
              - trakt_watched: accept
          test_trakt_collected_movie:
            trakt_lookup:
              username: flexgettest
            mock:
              - title: Inside.Out.2015.1080p.BDRip-FlexGet
              - title: The.Matrix.1999.1080p.BDRip-FlexGet
            if:
              - trakt_collected: accept
    """

    @use_vcr
    def test_trakt_watched_lookup(self):
        self.execute_task('test_trakt_watched')
        assert len(self.task.accepted) == 1, 'Episode should have been marked as watched and accepted'
        entry = self.task.accepted[0]
        assert entry['title'] == 'Hawaii.Five-0.S04E13.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Hawaii Five-0', 'wrong series was returned by lookup'
        assert entry['trakt_watched'] == True, 'episode should be marked as watched'

    @use_vcr
    def test_trakt_collected_lookup(self):
        self.execute_task('test_trakt_collected')
        assert len(self.task.accepted) == 1, 'Episode should have been marked as collected and accepted'
        entry = self.task.accepted[0]
        assert entry['title'] == 'Homeland.2011.S02E01.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Homeland 2011', 'wrong series was returned by lookup'
        assert entry['trakt_collected'] == True, 'episode should be marked as collected'

    @use_vcr
    def test_trakt_watched_movie_lookup(self):
        self.execute_task('test_trakt_watched_movie')
        assert len(self.task.accepted) == 1, 'Movie should have been accepted as it is watched on Trakt profile'
        entry = self.task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_watched'] == True, 'movie should be marked as watched'

    @use_vcr
    def test_trakt_collected_movie_lookup(self):
        self.execute_task('test_trakt_collected_movie')
        assert len(self.task.accepted) == 1, 'Movie should have been accepted as it is collected on Trakt profile'
        entry = self.task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_collected'] == True, 'movie should be marked as collected'


class TestTraktMovieLookup(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            trakt_lookup: yes
        tasks:
          test_lookup_sources:
            mock:
            - title: trakt id
              trakt_movie_id: 481
            - title: tmdb id
              tmdb_id: 603
            - title: imdb id
              imdb_id: tt0133093
            - title: slug
              trakt_movie_slug: the-matrix-1999
            - title: movie_name and movie_year
              movie_name: The Matrix
              movie_year: 1999
            - title: The Matrix (1999)
          test_lookup_actors:
            mock:
            - title: The Matrix (1999)
          test_search_results:
            mock:
            - title: harry.potter.and.the.philosopher's.stone.720p.hdtv-flexget
          test_search_results2:
            mock:
            - title: harry.potter.and.the.philosopher's.stone
    """

    @use_vcr
    def test_lookup_sources(self):
        self.execute_task('test_lookup_sources')
        for e in self.task.all_entries:
            assert e['movie_name'] == 'The Matrix', 'looking up based on %s failed' % e['title']

    @use_vcr
    def test_search_results(self):
        self.execute_task('test_search_results')
        entry = self.task.entries[0]
        assert entry['movie_name'].lower() == 'Harry Potter and The Philosopher\'s Stone'.lower(), 'lookup failed'
        with Session() as session:
            assert len(session.query(TraktMovieSearchResult).all()) == 1, 'should have added one movie to search result'

            # change the search query
            session.query(TraktMovieSearchResult).update({'search': "harry.potter.and.the.philosopher's"})
            session.commit()

            lookupargs = {'title': "harry.potter.and.the.philosopher's"}
            movie = ApiTrakt.lookup_movie(**lookupargs)

            assert movie.imdb_id == entry['imdb_id']
            assert movie.title.lower() == entry['movie_name'].lower()

    @use_vcr
    def test_lookup_actors(self):
        self.execute_task('test_lookup_actors')
        assert len(self.task.entries) == 1
        entry = self.task.entries[0]
        actors = ['Keanu Reeves',
                  'Laurence Fishburne',
                  'Carrie-Anne Moss',
                  'Hugo Weaving',
                  'Gloria Foster',
                  'Joe Pantoliano',
                  'Marcus Chong',
                  'Julian Arahanga',
                  'Matt Doran',
                  'Belinda McClory',
                  'Anthony Ray Parker',
                  'Paul Goddard',
                  'Robert Taylor',
                  'David Aston',
                  'Marc Aden',
                  'Ada Nicodemou',
                  'Deni Gordon',
                  'Rowan Witt',
                  'Bill Young',
                  'Eleanor Witt',
                  'Tamara Brown',
                  'Janaya Pender',
                  'Adryn White',
                  'Natalie Tjen',
                  'David O\'Connor',
                  'Jeremy Ball',
                  'Fiona Johnson',
                  'Harry Lawrence',
                  'Steve Dodd',
                  'Luke Quinton',
                  'Lawrence Woodward',
                  'Michael Butcher',
                  'Bernard Ledger',
                  'Robert Simper',
                  'Chris Pattinson',
                  'Nigel Harbach',
                  'Rana Morrison']
        trakt_actors = entry['trakt_movie_actors'].values()
        trakt_actors = [trakt_actor['name'] for trakt_actor in trakt_actors]
        assert entry['movie_name'] == 'The Matrix', 'movie lookup failed'
        assert set(trakt_actors) == set(actors), 'looking up actors for %s failed' % entry.get('title')
        assert entry['trakt_movie_actors']['7134']['name'] == 'Keanu Reeves', 'trakt id mapping failed'
        assert entry['trakt_movie_actors']['7134']['imdb_id'] == 'nm0000206', 'fetching imdb id for actor failed'
        assert entry['trakt_movie_actors']['7134']['tmdb_id'] == '6384', 'fetching tmdb id for actor failed'
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Keanu Reeves').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb_id == 'nm0000206', 'saving imdb_id for actors in table failed'
            assert actor.trakt_id == '7134', 'saving trakt_id for actors in table failed'
            assert actor.tmdb_id == '6384', 'saving tmdb_id for actors table failed'
