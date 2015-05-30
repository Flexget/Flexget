# TODO: these tests don't work outside US due imdb implementing geoip based crappy name translation
# imdb_name needs to be replaced with our own title lookup

"""
.. NOTE::

   Added `imdb_original_name` recently, so in case the title lookup translations cause problems
   switch to find_entry to use that instead!
"""

from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase, use_vcr


class TestImdb(FlexGetBase):

    __yaml__ = """
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
    """

    @use_vcr
    def test_lookup(self):
        """IMDB: Test Lookup (ONLINE)"""
        self.execute_task('test')
        assert self.task.find_entry(imdb_name='Spirited Away'), \
            'Failed IMDB lookup (search Spirited Away)'
        assert self.task.find_entry(imdb_name='Princess Mononoke'), \
            'Failed imdb lookup (direct)'
        assert self.task.find_entry(imdb_name='Taken', imdb_id='tt0936501'), \
            'Failed to pick correct Taken from search results'
        assert self.task.find_entry(imdb_id='tt1049413'), \
            'Failed to lookup Up.REPACK.720p.Bluray.x264-FlexGet'

    @use_vcr
    def test_year(self):
        self.execute_task('year')
        assert self.task.find_entry('accepted', imdb_name='Taken'), \
            'Taken should\'ve been accepted'
        # mononoke should not be accepted or rejected
        assert not self.task.find_entry('accepted', imdb_name='Mononoke-hime'), \
            'Mononoke-hime should not have been accepted'
        assert not self.task.find_entry('rejected', imdb_name='Mononoke-hime'), \
            'Mononoke-hime should not have been rejected'
        assert not self.task.find_entry('accepted', imdb_name='Inglourious Basterds 2009'), \
            'Inglourious Basterds should not have been accepted'

    @use_vcr
    def test_actors(self):
        self.execute_task('actor')

        # check that actors have been parsed properly
        matrix = self.task.find_entry(imdb_name='The Matrix')
        assert matrix, 'entry for matrix missing'

        assert 'nm0000206' in matrix['imdb_actors'], \
            'Keanu Reeves is missing'
        assert matrix['imdb_actors']['nm0000206'] == 'Keanu Reeves', \
            'Keanu Reeves name is missing'

        assert self.task.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.task.find_entry('rejected', imdb_name='The Terminator'), \
            'The The Terminator have been rejected'

    @use_vcr
    def test_directors(self):
        self.execute_task('director')
        # check that directors have been parsed properly
        matrix = self.task.find_entry(imdb_name='The Matrix')
        assert 'nm0905154' in matrix['imdb_directors'], \
            'Lana Wachowski is missing'
        assert matrix['imdb_directors']['nm0905154'] == 'Lana Wachowski', \
            'Lana Wachowski name is missing'

        assert self.task.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.task.find_entry('rejected', imdb_name='The Terminator'), \
            'The The Terminator have been rejected'

    @use_vcr
    def test_score(self):
        self.execute_task('score')
        assert self.task.find_entry(imdb_name='The Matrix'), 'The Matrix not found'
        matrix = float(self.task.find_entry(imdb_name='The Matrix')['imdb_score'])
        # Currently The Matrix has an 8.7, check a range in case it changes
        assert 8.6 < matrix < 8.8, \
            'The Matrix should have score 8.7 not %s. (Did the rating change?)' % matrix
        assert int(self.task.find_entry(imdb_name='The Matrix')['imdb_votes']) > 450000, \
            'The Matrix should have more than 450000 votes'
        bfe = float(self.task.find_entry(title='Battlefield Earth')['imdb_score'])
        # Currently Battlefield Earth has an 2.4, check a range in case it changes
        assert 2.3 <= bfe <= 2.5, \
            'Battlefield Earth should have score 2.3 not %s. (Did the rating change?)' % bfe
        assert self.task.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.task.find_entry('accepted', title='Battlefield Earth'), \
            'Battlefield Earth shouldn\'t have been accepted'

    @use_vcr
    def test_genre(self):
        self.execute_task('genre')
        matrix = (self.task.find_entry(imdb_name='The Matrix')['imdb_genres'])
        assert matrix == ['action', 'sci-fi'], \
            'Could not find genres for The Matrix'
        toe = (self.task.find_entry(imdb_name='Terms of Endearment')['imdb_genres'])
        assert toe == ['comedy', 'drama'], \
            'Could not find genres for Terms of Endearment'
        frozen = (self.task.find_entry(imdb_name='Frozen')['imdb_genres'])
        assert frozen == ['animation', 'adventure', 'comedy', 'family', 'fantasy', 'musical'], \
            'Could not find genres for Frozen'

        assert self.task.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.task.find_entry('rejected', title='Terms of Endearment'), \
            'Terms of Endearment should have been rejected'
        assert not self.task.find_entry('rejected', title='Frozen'), \
            'Frozen should have been rejected'

    @use_vcr
    def test_language(self):
        self.execute_task('language')
        matrix = self.task.find_entry(imdb_name='The Matrix')['imdb_languages']
        assert matrix == ['english'], 'Could not find languages for The Matrix'
        # IMDB may return imdb_name of "L'immortel" for 22 Bullets
        bullets = self.task.find_entry(imdb_original_name='L\'immortel')['imdb_languages']
        assert bullets[0] == 'french', 'Could not find languages for 22 Bullets'
        for movie in ['The Matrix', 'Crank', 'The Damned United']:
            assert self.task.find_entry('accepted', imdb_name=movie), \
                '%s should\'ve been accepted' % movie
        assert not self.task.find_entry('rejected', title='22 Bullets'), \
            '22 Bullets should have been rejected'
        # This test no longer valid (01/31/13) with IMDB language change
        # rockstar = self.task.find_entry(imdb_name='Rockstar')['imdb_languages']
        # # http://flexget.com/ticket/1399
        # assert rockstar == ['hindi'], 'Did not find only primary language'
        host_langs = self.task.find_entry(imdb_name='The Host')['imdb_languages']
        # switched to panjabi since that's what I got ...
        assert host_langs == ['korean', 'english'], \
            'Languages were not returned in order of prominence, got %s' % (', '.join(host_langs))

    @use_vcr
    def test_mpaa(self):
        self.execute_task('mpaa')
        aladdin = self.task.find_entry(imdb_name='Aladdin')
        assert aladdin['imdb_mpaa_rating'] == 'G', ('Didn\'t get right rating for Aladdin. Should be G got %s' %
                                                    aladdin['imdb_mpaa_rating'])
        assert aladdin.accepted, 'Non R rated movie should have been accepted'
        saw = self.task.find_entry(imdb_name='Saw')
        assert saw['imdb_mpaa_rating'] == 'R', 'Didn\'t get right rating for Saw'
        assert not saw.accepted, 'R rated movie should not have been accepted'


class TestImdbRequired(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'Taken[2008]DvDrip[Eng]-FOO', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'ASDFASDFASDF'}
            imdb_required: yes
    """

    @use_vcr
    def test_imdb_required(self):
        self.execute_task('test')
        assert not self.task.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), \
            'Taken should NOT have been rejected'
        assert self.task.find_entry('rejected', title='ASDFASDFASDF'), \
            'ASDFASDFASDF should have been rejected'


class TestImdbLookup(FlexGetBase):

    __yaml__ = """
        tasks:
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

    @use_vcr
    def test_invalid_url(self):
        self.execute_task('invalid url')
        # check that these were created
        assert self.task.entries[0]['imdb_score'], 'didn\'t get score'
        assert self.task.entries[0]['imdb_year'], 'didn\'t get year'
        assert self.task.entries[0]['imdb_plot_outline'], 'didn\'t get plot'

    @use_vcr(inject_cassette=True)
    def test_cache(self, cassette=None):
        # Hmm, this test doesn't work so well when in vcr 'all' record mode. It records new requests/responses
        # to the cassette, but still keeps the old recorded ones, causing this to fail.
        # Delete old cassette instead of using all mode to re-record.
        self.execute_task('cached')
        assert all(e['imdb_name'] == 'The Matrix' for e in self.task.all_entries)
        # If this is called with vcr turned off we won't have a cassette
        if cassette:
            # Should have only been one call to the actual imdb page
            imdb_calls = sum(1 for r in cassette.requests if 'title/tt0133093' in r.uri)
            assert imdb_calls == 1
