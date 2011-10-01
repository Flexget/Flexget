from tests import FlexGetBase


class TestProperMovies(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            seen_movies: strict
            accept_all: yes
            proper_movies: yes

        feeds:
          test1:
            mock:
              - {title: 'Movie.Name.2011.720p-FlexGet', imdb_id: 'tt12345678'}

          test2:
            mock:
              - {title: 'Movie.Name.2011.720p-FooBar', imdb_id: 'tt12345678'}

          test3:
            mock:
              - {title: 'Movie.Name.2011.PROPER.DVDRip-AsdfAsdf', imdb_id: 'tt12345678'}


          test4:
            mock:
              - {title: 'Movie.Name.2011.PROPER.720p-FlexGet', imdb_id: 'tt12345678'}
    """

    def test_proper_movies(self):
        # first occurence
        self.execute_feed('test1')
        assert self.feed.find_entry('accepted', title='Movie.Name.2011.720p-FlexGet')

        # duplicate movie
        self.execute_feed('test2')
        assert self.feed.find_entry('rejected', title='Movie.Name.2011.720p-FooBar')

        # proper with wrong quality
        self.execute_feed('test3')
        assert self.feed.find_entry('rejected', title='Movie.Name.2011.PROPER.DVDRip-AsdfAsdf')

        # proper version of same quality
        self.execute_feed('test4')
        assert self.feed.find_entry('accepted', title='Movie.Name.2011.PROPER.720p-FlexGet')
