# TODO: these tests don't work outside US due imdb implementing geoip based crappy name translation
# imdb_name needs to be replaced with our own title lookup

"""
.. NOTE::

   Added `imdb_original_name` recently, so in case the title lookup translations cause problems
   switch to find_entry to use that instead!
"""

import pytest


@pytest.mark.online
class TestImdb:
    config = """
        tasks:
          test:
            mock:
              # tests search
              - {title: 'Spirited Away'}
              # tests direct url
              - {title: 'Princess Mononoke', imdb_url: 'http://www.imdb.com/title/tt0119698/'}
              # generic test material, some tricky ones here :)
              - {title: 'Taken[2008]DvDrip[Eng]-FOO'}
              # test short title, with repack and without year
              - {title: 'Up.REPACK.720p.Bluray.x264-FlexGet'}
              # test (Video) result
              - {title: 'Futurama.Into.The.Wild.Green.Yonder.2009.PROPER'}
              # test (TV Movie) result
              - {title: 'Carny 2009'}
              # test confusing names for proper parsing
              - {title: 'Dan.In.Real.Life.2007'}
              - {title: 'The Final Cut.2004.720p.proper'}
              # tricky names for year parsing
              - {title: '2012 2009'}
              - {title: 'Red Riding In The Year Of Our Lord 1974 (2009) 720p BRrip X264'}
              - {title: 'Nightmare City 2035 (2007) DVDRip'}
              # test a movie that is far from the top in search results
              - {title: 'The Hunter 2010'}
              # test a search in which a movie has lower relevance than tv episodes
              - {title: 'Mad Max Fury Road 2015'}
            imdb:
              min_votes: 20

          year:
            mock:
              - {title: 'Princess Mononoke', imdb_url: 'http://www.imdb.com/title/tt0119698/'}
              - {title: 'Taken[2008]DvDrip[Eng]-FOO', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'Inglourious Basterds 2009', imdb_url: 'http://www.imdb.com/title/tt0361748/'}
            imdb:
              min_year: 2003
              max_year: 2008

          actor:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: 'The Terminator', imdb_url: 'http://www.imdb.com/title/tt0088247/'}
            imdb:
              accept_actors:
                - nm0000206
              reject_actors:
                - nm0000216

          director:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: 'The Terminator', imdb_url: 'http://www.imdb.com/title/tt0088247/'}
            imdb:
              accept_directors:
                - nm0905152
                - nm0905154
              reject_directors:
                - nm0000116

          writer:
            mock:
              - {title: 'Hot Fuzz', imdb_url: 'http://www.imdb.com/title/tt0425112/'}
              - {title: 'The Terminator', imdb_url: 'http://www.imdb.com/title/tt0088247/'}
            imdb:
              accept_writers:
                - nm0942367
                - nm0670408
              reject_writers:
                - nm0000116

          score:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: 'Battlefield Earth', imdb_url: 'http://www.imdb.com/title/tt0185183/'}
            imdb:
              min_score: 5.0

          genre:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: 'Terms of Endearment', imdb_url: 'http://www.imdb.com/title/tt0086425/'}
              - {title: 'Frozen', imdb_url: 'http://www.imdb.com/title/tt2294629/'}
            imdb:
              reject_genres:
                - drama
              accept_genres:
                - sci-fi

          language:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: '22 Bullets', imdb_url: 'http://www.imdb.com/title/tt1167638/'}
              - {title: 'Crank', imdb_url: 'http://www.imdb.com/title/tt0479884/'}
              - {title: 'The Damned United', imdb_url: 'http://www.imdb.com/title/tt1226271/'}
              - {title: 'Rockstar', imdb_url: 'http://www.imdb.com/title/tt1839596/'}
              - {title: 'The Host', imdb_url: 'http://www.imdb.com/title/tt0468492/'}
            imdb:
              accept_languages:
                - english
              reject_languages:
                - french
          mpaa:
            mock:
            - title: Saw 2004
              imdb_url: http://www.imdb.com/title/tt0387564/
            - title: Aladdin 1992
              imdb_url: http://www.imdb.com/title/tt0103639/
            imdb:
              reject_mpaa_ratings:
              - R

          imdb_identifier:
            imdb_lookup: yes
            mock:
              - {title: 'The.Matrix.720p.WEB-DL.X264.AC3'}

    """

    def test_lookup(self, execute_task):
        """IMDB: Test Lookup (ONLINE)"""
        task = execute_task('test')
        assert task.find_entry(imdb_name='Spirited Away'), (
            'Failed IMDB lookup (search Spirited Away)'
        )
        assert task.find_entry(imdb_name='Princess Mononoke'), 'Failed imdb lookup (direct)'
        assert task.find_entry(imdb_name='Taken', imdb_id='tt0936501'), (
            'Failed to pick correct Taken from search results'
        )
        assert task.find_entry(imdb_id='tt1049413'), (
            'Failed to lookup Up.REPACK.720p.Bluray.x264-FlexGet'
        )
        assert task.find_entry(imdb_id='tt1054487'), (
            'Failed to lookup Futurama.Into.The.Wild.Green.Yonder.2009.PROPER'
        )
        assert task.find_entry(imdb_id='tt1397497'), 'Failed to lookup Carny 2009'
        assert task.find_entry(imdb_id='tt0364343'), (
            'Failed to lookup The Final Cut.2004.720p.proper'
        )
        assert task.find_entry(imdb_id='tt0480242'), 'Failed to lookup Dan.In.Real.Life.2007'
        assert task.find_entry(imdb_id='tt1190080'), 'Failed to lookup 2012 2009'
        assert task.find_entry(imdb_id='tt1259574'), (
            'Failed to lookup Red Riding In The Year Of Our Lord 1974 (2009) 720p BRrip X264'
        )
        assert task.find_entry(imdb_id='tt0910868'), (
            'Failed to lookup Nightmare City 2035 (2007) DVDRip'
        )
        assert task.find_entry(imdb_id='tt1190072'), 'Failed to lookup The Hunter 2010'
        assert task.find_entry(imdb_id='tt1392190'), 'Failed to lookup Mad Max Fury Road 2015'

    def test_year(self, execute_task):
        task = execute_task('year')
        assert task.find_entry('accepted', imdb_name='Taken'), 'Taken should\'ve been accepted'
        # mononoke should not be accepted or rejected
        assert not task.find_entry('accepted', imdb_name='Mononoke-hime'), (
            'Mononoke-hime should not have been accepted'
        )
        assert not task.find_entry('rejected', imdb_name='Mononoke-hime'), (
            'Mononoke-hime should not have been rejected'
        )
        assert not task.find_entry('accepted', imdb_name='Inglourious Basterds 2009'), (
            'Inglourious Basterds should not have been accepted'
        )

    def test_actors(self, execute_task):
        task = execute_task('actor')

        # check that actors have been parsed properly
        matrix = task.find_entry(imdb_name='The Matrix')
        assert matrix, 'entry for matrix missing'

        assert 'nm0000206' in matrix['imdb_actors'], 'Keanu Reeves is missing'
        assert matrix['imdb_actors']['nm0000206'] == 'Keanu Reeves', 'Keanu Reeves name is missing'

        assert task.find_entry('accepted', imdb_name='The Matrix'), (
            'The Matrix should\'ve been accepted'
        )
        assert not task.find_entry('rejected', imdb_name='The Terminator'), (
            'The The Terminator have been rejected'
        )

    def test_directors(self, execute_task):
        task = execute_task('director')
        # check that directors have been parsed properly
        matrix = task.find_entry(imdb_name='The Matrix')
        assert 'nm0905154' in matrix['imdb_directors'], 'Lana Wachowski is missing'
        assert matrix['imdb_directors']['nm0905154'] == 'Lana Wachowski', (
            'Lana Wachowski name is missing'
        )

        assert task.find_entry('accepted', imdb_name='The Matrix'), (
            'The Matrix should\'ve been accepted'
        )
        assert not task.find_entry('rejected', imdb_name='The Terminator'), (
            'The The Terminator have been rejected'
        )

    def test_writers(self, execute_task):
        task = execute_task('writer')

        # check that writers have been parsed properly
        hotfuzz = task.find_entry(imdb_name='Hot Fuzz')
        assert hotfuzz, 'entry for Hot Fuzz missing'

        assert 'nm0942367' in hotfuzz['imdb_writers'], 'Edgar Wright is missing'
        assert hotfuzz['imdb_writers']['nm0942367'] == 'Edgar Wright', (
            'Edgar Wright name is missing'
        )

        assert task.find_entry('accepted', imdb_name='Hot Fuzz'), (
            'Hot Fuzz should\'ve been accepted'
        )
        assert not task.find_entry('rejected', imdb_name='The Terminator'), (
            'The Terminator have been rejected'
        )

    def test_score(self, execute_task):
        task = execute_task('score')
        assert task.find_entry(imdb_name='The Matrix'), 'The Matrix not found'
        matrix = float(task.find_entry(imdb_name='The Matrix')['imdb_score'])
        # Currently The Matrix has an 8.7, check a range in case it changes
        assert 8.6 < matrix < 8.8, (
            f'The Matrix should have score 8.7 not {matrix}. (Did the rating change?)'
        )
        assert int(task.find_entry(imdb_name='The Matrix')['imdb_votes']) > 450000, (
            'The Matrix should have more than 450000 votes'
        )
        bfe = float(task.find_entry(title='Battlefield Earth')['imdb_score'])
        # Currently Battlefield Earth has an 2.4, check a range in case it changes
        assert 2.3 <= bfe <= 2.5, (
            f'Battlefield Earth should have score 2.3 not {bfe}. (Did the rating change?)'
        )
        assert task.find_entry('accepted', imdb_name='The Matrix'), (
            'The Matrix should\'ve been accepted'
        )
        assert not task.find_entry('accepted', title='Battlefield Earth'), (
            'Battlefield Earth shouldn\'t have been accepted'
        )

    def test_genre(self, execute_task):
        task = execute_task('genre')
        matrix = task.find_entry(imdb_name='The Matrix')['imdb_genres']
        assert matrix == ['action', 'sci-fi'], 'Could not find genres for The Matrix'
        toe = task.find_entry(imdb_name='Terms of Endearment')['imdb_genres']
        assert toe == ['comedy', 'drama'], 'Could not find genres for Terms of Endearment'
        frozen = task.find_entry(imdb_name='Frozen')['imdb_genres']
        assert frozen == [
            'animation',
            'adventure',
            'comedy',
            'family',
            'fantasy',
            'musical',
        ], 'Could not find genres for Frozen'

        assert task.find_entry('accepted', imdb_name='The Matrix'), (
            'The Matrix should\'ve been accepted'
        )
        assert not task.find_entry('rejected', title='Terms of Endearment'), (
            'Terms of Endearment should have been rejected'
        )
        assert not task.find_entry('rejected', title='Frozen'), 'Frozen should have been rejected'

    def test_language(self, execute_task):
        task = execute_task('language')
        matrix = task.find_entry(imdb_name='The Matrix')['imdb_languages']
        assert matrix == ['english'], 'Could not find languages for The Matrix'
        # IMDB may return imdb_name of "L'immortel" for 22 Bullets
        bullets = task.find_entry(imdb_original_name='L\'immortel')['imdb_languages']
        assert bullets[0] == 'french', 'Could not find languages for 22 Bullets'
        for movie in ['The Matrix', 'Crank', 'The Damned United']:
            assert task.find_entry('accepted', imdb_name=movie), (
                f'{movie} should\'ve been accepted'
            )
        assert not task.find_entry('rejected', title='22 Bullets'), (
            '22 Bullets should have been rejected'
        )
        rockstar = task.find_entry(imdb_name='Rockstar')['imdb_languages']
        # http://flexget.com/ticket/1399
        assert rockstar == ['hindi'], 'Did not find only primary language'
        host_langs = task.find_entry(imdb_name='The Host')['imdb_languages']
        # switched to panjabi since that's what I got ...
        assert host_langs == [
            'korean',
            'english',
        ], 'Languages were not returned in order of prominence, got {}'.format(
            ', '.join(host_langs)
        )

    def test_mpaa(self, execute_task):
        task = execute_task('mpaa')
        aladdin = task.find_entry(imdb_name='Aladdin')
        assert aladdin['imdb_mpaa_rating'] == 'G', (
            'Didn\'t get right rating for Aladdin. Should be G got {}'.format(
                aladdin['imdb_mpaa_rating']
            )
        )
        assert aladdin.accepted, 'Non R rated movie should have been accepted'
        saw = task.find_entry(imdb_name='Saw')
        assert saw['imdb_mpaa_rating'] == 'R', 'Didn\'t get right rating for Saw'
        assert not saw.accepted, 'R rated movie should not have been accepted'


@pytest.mark.online
class TestImdbLookup:
    config = """
        tasks:
          identifier:
            mock:
              - {title: 'Taken 720p'}
            imdb_lookup: yes
          invalid url:
            mock:
              - {title: 'Taken', imdb_url: 'imdb.com/title/tt0936501/'}
            imdb_lookup: yes
          cached:
            mock:
              - title: The Matrix 1999 720p
              - title: The Matrix 1080p
              - title: The Matrix xvid
            imdb_lookup: yes

    """

    def test_invalid_url(self, execute_task):
        task = execute_task('invalid url')
        # check that these were created
        assert task.entries[0]['imdb_score'], 'didn\'t get score'
        assert task.entries[0]['imdb_year'], 'didn\'t get year'
        assert task.entries[0]['imdb_plot_outline'], 'didn\'t get plot'

    def test_cache(self, execute_task, use_vcr):
        # Hmm, this test doesn't work so well when in vcr 'all' record mode. It records new requests/responses
        # to the cassette, but still keeps the old recorded ones, causing this to fail.
        # Delete old cassette instead of using all mode to re-record.
        task = execute_task('cached')
        assert all(e['imdb_name'] == 'The Matrix' for e in task.all_entries)
        # If this is called with vcr turned off we won't have a cassette
        if use_vcr:
            # Should have only been one call to the actual imdb page
            imdb_calls = sum(1 for r in use_vcr.requests if 'title/tt0133093' in r.uri)
            assert imdb_calls == 1
