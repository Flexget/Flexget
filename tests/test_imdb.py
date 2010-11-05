from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestImdb(FlexGetBase):

    __yaml__ = """
        feeds:
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
            imdb:
              min_year: 2003

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
            imdb:
              reject_genres:
                - drama
            # No accept_genres?!
            accept_all: yes

          language:
            mock:
              - {title: 'The Matrix', imdb_url: 'http://www.imdb.com/title/tt0133093/'}
              - {title: '22 Bullets', imdb_url: 'http://www.imdb.com/title/tt1167638/'}
            imdb:
              accept_languages:
                - english
              reject_languages:
                - french
    """

    @attr(online=True)
    def test_lookup(self):
        """IMDB: Test Lookup (ONLINE)"""
        self.execute_feed('test')
        assert self.feed.find_entry(imdb_name='Spirited Away'), \
            'Failed IMDB lookup (search chihiro)'
        assert self.feed.find_entry(imdb_name='Princess Mononoke'), \
            'Failed imdb lookup (direct)'
        assert self.feed.find_entry(imdb_name='Taken', imdb_url='http://www.imdb.com/title/tt0936501/'), \
            'Failed to pick correct Taken from search results'
        assert self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt1049413/'), \
            'Failed to lookup Up.REPACK.720p.Bluray.x264-FlexGet'

    @attr(online=True)
    def test_year(self):
        self.execute_feed('year')
        assert self.feed.find_entry('accepted', imdb_name='Taken'), \
            'Taken should\'ve been accepted'
        # mononoke should not be accepted or rejected
        assert not self.feed.find_entry('accepted', imdb_name='Mononoke-hime'), \
            'Mononoke-hime should not have been accepted'
        assert not self.feed.find_entry('rejected', imdb_name='Mononoke-hime'), \
            'Mononoke-hime should not have been rejected'

    @attr(online=True)
    def test_actors(self):
        self.execute_feed('actor')

        # check that actors have been parsed properly
        matrix = self.feed.find_entry(imdb_name='The Matrix')
        assert 'nm0000206' in matrix['imdb_actors'], \
            'Keanu Reeves is missing'
        assert matrix['imdb_actors']['nm0000206'] == 'Keanu Reeves', \
            'Keanu Reeves name is missing'

        assert self.feed.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.feed.find_entry('rejected', imdb_name='The Terminator'), \
            'The The Terminator have been rejected'

    # TODO: html parsing needs updating to account for new imdb layout
    @attr(online=True)
    def _test_directors(self):
        self.execute_feed('director')
        # check that directors have been parsed properly
        matrix = self.feed.find_entry(imdb_name='The Matrix')
        assert 'nm0905154' in matrix['imdb_directors'], \
            'Lana Wachowski is missing'
        assert matrix['imdb_directors']['nm0905154'] == 'Lana Wachowski', \
            'Lana Wachowski name is missing'

        assert self.feed.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.feed.find_entry('rejected', imdb_name='The Terminator'), \
            'The The Terminator have been rejected'

    @attr(online=True)
    def test_score(self):
        self.execute_feed('score')
        matrix = float(self.feed.find_entry(imdb_name='The Matrix')['imdb_score'])
        # Currently The Matrix has an 8.7, check a range in case it changes
        assert matrix > 8.6 and matrix < 8.8, \
            'The Matrix should have score 8.7 not %s. (Did the rating change?)' % matrix
        bfe = float(self.feed.find_entry(title='Battlefield Earth')['imdb_score'])
        # Currently Battlefield Earth has an 2.3, check a range in case it changes
        assert bfe > 2.2 and bfe < 2.4, \
            'Battlefield Earth should have score 2.3 not %s. (Did the rating change?)' % bfe
        assert self.feed.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.feed.find_entry('accepted', title='Battlefield Earth'), \
            'Battlefield Earth shouldn\'t have been accepted'

    @attr(online=True)
    def test_genre(self):
        self.execute_feed('genre')
        matrix = (self.feed.find_entry(imdb_name='The Matrix')['imdb_genres'])
        assert matrix == ['action', 'adventure', 'sci-fi'], \
            'Could not find genres for The Matrix'
        toe = (self.feed.find_entry(imdb_name='Terms of Endearment')['imdb_genres'])
        assert toe == ['romance', 'comedy', 'drama'], \
            'Could not find genres for Terms of Endearment'
        assert self.feed.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.feed.find_entry('rejected', title='Terms of Endearment'), \
            'Terms of Endearment should have been rejected'

    @attr(online=True)
    def test_language(self):
        self.execute_feed('language')
        matrix = (self.feed.find_entry(imdb_name='The Matrix')['imdb_languages'])
        assert matrix == ['english'], \
            'Could not find languages for The Matrix'
        bullets = (self.feed.find_entry(imdb_name='22 Bullets')['imdb_languages'])
        assert bullets == ['french'], \
            'Could not find languages for 22 Bullets'
        assert self.feed.find_entry('accepted', imdb_name='The Matrix'), \
            'The Matrix should\'ve been accepted'
        assert not self.feed.find_entry('rejected', title='22 Bullets'), \
            '22 Bullets should have been rejected'


class TestImdbRequired(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Taken[2008]DvDrip[Eng]-FOO', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'ASDFASDFASDF'}
            imdb_required: yes
    """

    @attr(online=True)
    def test_imdb_required(self):
        self.execute_feed('test')
        assert not self.feed.find_entry('rejected', title='Taken[2008]DvDrip[Eng]-FOO'), \
            'Taken should NOT have been rejected'
        assert self.feed.find_entry('rejected', title='ASDFASDFASDF'), \
            'ASDFASDFASDF should have been rejected'


class TestImdbLookup(FlexGetBase):

    __yaml__ = """
        feeds:
          invalid url:
            mock:
              - {title: 'Taken', imdb_url: 'imdb.com/title/tt0936501/'}
            imdb_lookup: yes
    """

    @attr(online=True)
    def test_invalid_url(self):
        self.execute_feed('invalid url')
        # check that these were created
        assert self.feed.entries[0]['imdb_score'], 'didn\'t get score'
        assert self.feed.entries[0]['imdb_year'], 'didn\'t get year'
