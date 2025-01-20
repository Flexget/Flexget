import pytest

from flexget.components.trakt.api import ObjectsContainer as OC
from flexget.components.trakt.api_trakt import ApiTrakt
from flexget.components.trakt.db import (
    TraktActor,
    TraktMovieSearchResult,
    TraktShow,
    TraktShowSearchResult,
)
from flexget.manager import Session

lookup_series = ApiTrakt.lookup_series


@pytest.mark.online
class TestTraktShowLookup:
    config = """
        templates:
          global:
            trakt_lookup: yes
            # Access a trakt field to cause lazy loading to occur
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
              - the daily show (with trevor noah)
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
          test_search_success:
            mock:
              - {title: '11-22-63.S01E01.HDTV.XViD-FlexGet'}
            series:
              - 11-22-63
          test_alternate_language:
            mock:
              - {'title': 'Игра престолов (2011).s01e01.hdtv'}
            series:
              - Игра престолов
          test_lookup_translations:
            mock:
              - {title: 'Game.Of.Thrones.S01E02.HDTV.XViD-FlexGet'}
            series:
              - Game Of Thrones
          test_season_lookup:
            mock:
              - {title: 'Fargo.S01.1080p.BluRay-FlexGet'}
            series:
              - Fargo:
                  season_packs: yes
    """

    def test_lookup_name(self, execute_task):
        """trakt: Test Lookup (ONLINE)"""
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_show_id'] == 1399, 'Trakt_ID should be 1339 is {} for {}'.format(
            entry['trakt_show_id'],
            entry['series_name'],
        )
        assert entry['trakt_series_status'] == 'ended', (
            'Series Status should be "ENDED" returned {}'.format(entry['trakt_series_status'])
        )

    def test_lookup(self, execute_task):
        """trakt: Test Lookup (ONLINE)"""
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_ep_name'] == 'Paternity', (
            '{} trakt_ep_name should be Paternity'.format(entry['title'])
        )
        assert entry['trakt_series_status'] == 'ended', (
            'runtime for {} is {}, should be "ended"'.format(
                entry['title'],
                entry['trakt_series_status'],
            )
        )
        assert entry['afield'] == '73255Paternity', 'afield was not set correctly'
        assert task.find_entry(trakt_ep_name='School Reunion'), (
            'Failed imdb lookup Doctor Who 2005 S02E03'
        )

    def test_unknown_series(self, execute_task):
        # Test an unknown series does not cause any exceptions
        task = execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    def test_search_results(self, execute_task):
        task = execute_task('test_search_result')
        entry = task.entries[0]
        print(entry['trakt_series_name'].lower())
        assert entry['trakt_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        with Session() as session:
            assert task.entries[1]['trakt_series_name'].lower() == 'Shameless'.lower(), (
                'second lookup failed'
            )

            assert len(session.query(TraktShowSearchResult).all()) == 1, (
                'should have added 1 show to search result'
            )

            assert len(session.query(TraktShow).all()) == 1, (
                'should only have added one show to show table'
            )
            assert session.query(TraktShow).first().title == 'Shameless', (
                'should have added Shameless and not Shameless (2010)'
            )
            # change the search query
            session.query(TraktShowSearchResult).update(
                {'search': "shameless.s01e03.hdtv-flexget"}
            )
            session.commit()

            lookupargs = {'title': "Shameless.S01E03.HDTV-FlexGet"}
            series = ApiTrakt.lookup_series(session=session, **lookupargs)

            assert series.tvdb_id == entry['tvdb_id'], (
                'tvdb id should be the same as the first entry'
            )
            assert series.id == entry['trakt_show_id'], (
                'trakt id should be the same as the first entry'
            )
            assert series.title.lower() == entry['trakt_series_name'].lower(), (
                'series name should match first entry'
            )

    def test_search_success(self, execute_task):
        task = execute_task('test_search_success')
        entry = task.find_entry('accepted', title='11-22-63.S01E01.HDTV.XViD-FlexGet')
        assert entry.get('trakt_show_id') == 102771, 'Should have returned the correct trakt id'

    def test_date(self, execute_task):
        task = execute_task('test_date')
        entry = task.find_entry(title='the daily show 2012-6-6')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 2211, 'should have populated trakt show data'
        # We don't support lookup by date at the moment, make sure there isn't a false positive
        if entry.get('trakt_episode_id') == 173423:
            raise AssertionError(
                'We support trakt episode lookup by date now? Great! Change this test.'
            )
        assert entry.get('trakt_episode_id') is None, (
            'false positive for episode match, we don\'t support lookup by date'
        )

    def test_absolute(self, execute_task):
        task = execute_task('test_absolute')
        entry = task.find_entry(title='naruto 128')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 46003, 'should have populated trakt show data'
        # We don't support lookup by absolute number at the moment, make sure there isn't a false positive
        if entry.get('trakt_show_id') == 916040:
            raise AssertionError(
                'We support trakt episode lookup by absolute number now? Great! Change this test.'
            )
        assert entry.get('trakt_episode_id') is None, (
            'false positive for episode match, we don\'t support lookup by absolute number'
        )

    def test_lookup_actors(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['series_name'] == 'House', 'series lookup failed'
        assert entry['trakt_actors']['297390']['name'] == 'Hugh Laurie', 'trakt id mapping failed'
        assert entry['trakt_actors']['297390']['imdb_id'] == 'nm0491402', (
            'fetching imdb id for actor failed'
        )
        assert entry['trakt_actors']['297390']['tmdb_id'] == '41419', (
            'fetching tmdb id for actor failed'
        )
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Hugh Laurie').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb == 'nm0491402', 'saving imdb_id for actors in table failed'
            assert str(actor.id) == '297390', 'saving trakt_id for actors in table failed'
            assert str(actor.tmdb) == '41419', 'saving tmdb_id for actors table failed'

    def test_lookup_translations(self, execute_task, schema_match):
        task = execute_task('test_lookup_translations')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['series_name'] == 'Game Of Thrones', 'series lookup failed'
        errors = schema_match(OC.translation_object, entry['trakt_translations'])
        assert not errors

    def test_season_lookup(self, execute_task):
        task = execute_task('test_season_lookup')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['series_name'] == 'Fargo', 'series lookup failed'
        assert entry['series_season'] == 1 and entry['season_pack'], 'season lookup failed'
        assert entry['trakt_season_id'] == 61286, 'season lookup failed'


@pytest.mark.online
class TestTraktList:
    config = """
        tasks:
          test_trakt_movies:
            trakt_list:
              username: flexgettest
              list: watchlist
              type: movies
    """

    def test_trakt_movies(self, execute_task):
        task = execute_task('test_trakt_movies')
        assert len(task.entries) == 1
        entry = task.entries[0]
        assert entry['title'] == '12 Angry Men (1957)'
        assert entry['movie_name'] == '12 Angry Men'
        assert entry['movie_year'] == 1957
        assert entry['imdb_id'] == 'tt0050083'


@pytest.mark.online
class TestTraktWatchedAndCollected:
    config = """
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
          test_trakt_show_collected_progress:
            disable: builtins
            trakt_lookup:
              username: flexgettest
            trakt_list:
              username: flexgettest
              list: test
              type: shows
            if:
              - trakt_collected: accept
          test_trakt_show_watched_progress:
            disable: builtins
            trakt_lookup:
              username: flexgettest
            trakt_list:
              username: flexgettest
              list: test
              type: shows
            if:
              - trakt_watched: accept
          test_trakt_season_collected:
            disable: builtins
            metainfo_series: yes
            trakt_lookup:
              username: flexgettest
            mock:
              - {title: 'The.Expanse.S01.720p.BluRay-FlexGet'}
            if:
              - trakt_collected: accept
          test_trakt_season_watched:
            disable: builtins
            metainfo_series: yes
            trakt_lookup:
              username: flexgettest
            mock:
              - {title: 'Into.The.Badlands.S01.720p.BluRay-FlexGet'}
            if:
              - trakt_watched: accept
          test_trakt_user_lookup_fail:
            disable: builtins
            trakt_lookup:
              username: flexgettest
            mock:
              - title: aoetaraeha aeotrae taetaeor

    """

    def test_trakt_watched_lookup(self, execute_task):
        task = execute_task('test_trakt_watched')
        assert len(task.accepted) == 1, 'Episode should have been marked as watched and accepted'
        entry = task.accepted[0]
        assert entry['title'] == 'Hawaii.Five-0.S04E13.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Hawaii Five-0', 'wrong series was returned by lookup'
        assert entry['trakt_watched'] is True, 'episode should be marked as watched'

    def test_trakt_collected_lookup(self, execute_task):
        task = execute_task('test_trakt_collected')
        assert len(task.accepted) == 1, 'Episode should have been marked as collected and accepted'
        entry = task.accepted[0]
        assert entry['title'] == 'Homeland.2011.S02E01.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Homeland 2011', 'wrong series was returned by lookup'
        assert entry['trakt_collected'] is True, 'episode should be marked as collected'

    def test_trakt_watched_movie_lookup(self, execute_task):
        task = execute_task('test_trakt_watched_movie')
        assert len(task.accepted) == 1, (
            'Movie should have been accepted as it is watched on Trakt profile'
        )
        entry = task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_watched'] is True, 'movie should be marked as watched'

    def test_trakt_collected_movie_lookup(self, execute_task):
        task = execute_task('test_trakt_collected_movie')
        assert len(task.accepted) == 1, (
            'Movie should have been accepted as it is collected on Trakt profile'
        )
        entry = task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_collected'] is True, 'movie should be marked as collected'

    def test_trakt_show_watched_progress(self, execute_task):
        task = execute_task('test_trakt_show_watched_progress')
        assert len(task.accepted) == 1, (
            'One show should have been accepted as it is watched on Trakt profile'
        )
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'Chuck', 'wrong series was accepted'
        assert entry['trakt_watched'] is True, 'the whole series should be marked as watched'

    def test_trakt_show_collected_progress(self, execute_task):
        task = execute_task('test_trakt_show_collected_progress')
        assert len(task.accepted) == 1, (
            'One show should have been accepted as it is collected on Trakt profile'
        )
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'White Collar', 'wrong series was accepted'
        assert entry['trakt_collected'] is True, 'the whole series should be marked as collected'

    def test_trakt_season_collected(self, execute_task):
        task = execute_task('test_trakt_season_collected')
        assert len(task.accepted) == 1, 'Entry should have been accepted as it has been collected'
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'The Expanse', 'wrong series was accepted'
        assert entry['trakt_collected'] is True, 'the whole season should be marked as collected'

    def test_trakt_season_watched(self, execute_task):
        task = execute_task('test_trakt_season_watched')
        assert len(task.accepted) == 1, 'Entry should have been accepted as it has been watched'
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'Into the Badlands', 'wrong series was accepted'
        assert entry['trakt_watched'] is True, 'the whole season should be marked as watched'

    def test_trakt_user_lookup_fail(self, execute_task):
        # Just making sure we don't crash. See #2606
        task = execute_task('test_trakt_user_lookup_fail')
        for e in task.entries:
            assert 'trakt_watched' not in e or not e['trakt_watched']
            assert 'trakt_collected' not in e or not e['trakt_collected']


@pytest.mark.online
class TestTraktMovieLookup:
    config = """
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
          test_lookup_translations:
            mock:
            - title: The Matrix Reloaded (2003)
    """

    def test_lookup_sources(self, execute_task):
        task = execute_task('test_lookup_sources')
        for e in task.all_entries:
            assert e['movie_name'] == 'The Matrix', 'looking up based on {} failed'.format(
                e['title']
            )

    def test_search_results(self, execute_task):
        task = execute_task('test_search_results')
        entry = task.entries[0]
        assert (
            entry['movie_name'].lower() == 'Harry Potter and The Philosopher\'s Stone'.lower()
        ), 'lookup failed'
        with Session() as session:
            assert len(session.query(TraktMovieSearchResult).all()) == 1, (
                'should have added one movie to search result'
            )

            # change the search query
            session.query(TraktMovieSearchResult).update(
                {'search': "harry.potter.and.the.philosopher's"}
            )
            session.commit()

            lookupargs = {'title': "harry.potter.and.the.philosopher's"}
            movie = ApiTrakt.lookup_movie(session=session, **lookupargs)

            assert movie.imdb_id == entry['imdb_id']
            assert movie.title.lower() == entry['movie_name'].lower()

    def test_lookup_actors(self, execute_task):
        task = execute_task('test_lookup_actors')
        assert len(task.entries) == 1
        entry = task.entries[0]
        actors = [
            'Keanu Reeves',
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
            'Rana Morrison',
            'Robert Taylor',
            'David Aston',
            'Marc Aden Gray',
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
        ]
        trakt_actors = list(entry['trakt_actors'].values())
        trakt_actors = [trakt_actor['name'] for trakt_actor in trakt_actors]
        assert entry['movie_name'] == 'The Matrix', 'movie lookup failed'
        assert set(trakt_actors) == set(actors), 'looking up actors for {} failed'.format(
            entry.get('title')
        )
        assert entry['trakt_actors']['7134']['name'] == 'Keanu Reeves', 'trakt id mapping failed'
        assert entry['trakt_actors']['7134']['imdb_id'] == 'nm0000206', (
            'fetching imdb id for actor failed'
        )
        assert entry['trakt_actors']['7134']['tmdb_id'] == '6384', (
            'fetching tmdb id for actor failed'
        )
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Keanu Reeves').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb == 'nm0000206', 'saving imdb_id for actors in table failed'
            assert str(actor.id) == '7134', 'saving trakt_id for actors in table failed'
            assert str(actor.tmdb) == '6384', 'saving tmdb_id for actors table failed'

    def test_lookup_translations(self, execute_task, schema_match):
        task = execute_task('test_lookup_translations')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['movie_name'] == 'The Matrix Reloaded', 'movie lookup failed'
        errors = schema_match(OC.translation_object, entry['trakt_translations'])
        assert not errors, 'JSON schema does not match'


@pytest.mark.online
class TestTraktUnicodeLookup:
    config = """
        templates:
          global:
            trakt_lookup: yes
        tasks:
          test_unicode:
            disable: seen
            mock:
                - {'title': '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008', 'url': 'mock://whatever'}
            if:
                - trakt_year > now.year - 1: reject
    """

    @pytest.mark.xfail(reason='VCR attempts to compare str to unicode')
    def test_unicode(self, execute_task):
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should have added a search result'
            assert (
                r[0].search == '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008'.lower()
            ), 'The search result should be lower case'
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should not have added a new row'


@pytest.mark.online
class TestTraktRatingsLookup:
    config = """
            templates:
              global:
                trakt_lookup:
                  username: flexgettest
                metainfo_series: yes
            tasks:
              test_trakt_ratings_episode:
                mock:
                  - {title: 'Breaking.Bad.S05E14.720p.HDTV-FlexGet'}
              test_trakt_ratings_season:
                mock:
                  - {title: 'The.Expanse.S01.2160p.WEBRip-FlexGet'}
              test_trakt_ratings_show:
                mock:
                  - {title: 'Time.After.Time.2017.S01E01.HDTV-FlexGet'}
              test_trakt_ratings_movie:
                mock:
                  - {title: 'Doctor.Strange.2016.1080p.BluRay.DTS-FlexGet'}

        """

    def test_trakt_ratings_episode(self, execute_task):
        task = execute_task('test_trakt_ratings_episode')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['trakt_ep_user_rating'] == 10, 'Wrong rating received for Ozymandias'

    def test_trakt_ratings_season(self, execute_task):
        task = execute_task('test_trakt_ratings_season')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['trakt_season_user_rating'] == 10, (
            'Wrong rating received for Season 1 of The Expanse'
        )

    def test_trakt_ratings_show(self, execute_task):
        task = execute_task('test_trakt_ratings_show')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['trakt_series_user_rating'] == 1, (
            'Wrong rating received for Time After Time 2017'
        )

    def test_trakt_ratings_movie(self, execute_task):
        task = execute_task('test_trakt_ratings_movie')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['trakt_movie_user_rating'] == 9, 'Wrong rating received for Doctor Strange'
