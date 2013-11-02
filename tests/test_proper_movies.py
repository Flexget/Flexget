from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestProperMovies(FlexGetBase):

    __yaml__ = """
        templates:
          global:
            seen_movies: strict
            accept_all: yes
            proper_movies: yes

        tasks:
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
        self.execute_task('test1')
        assert self.task.find_entry('accepted', title='Movie.Name.2011.720p-FlexGet')

        # duplicate movie
        self.execute_task('test2')
        assert self.task.find_entry('rejected', title='Movie.Name.2011.720p-FooBar')

        # proper with wrong quality
        self.execute_task('test3')
        assert self.task.find_entry('rejected', title='Movie.Name.2011.PROPER.DVDRip-AsdfAsdf')

        # proper version of same quality
        self.execute_task('test4')
        assert self.task.find_entry('accepted', title='Movie.Name.2011.PROPER.720p-FlexGet')
