from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestTmdbLookup(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: '[Group] Taken 720p', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'The Matrix'}
            tmdb_lookup: yes
            # Access a field to cause lazy loading to occur
            set:
              afield: "{{ tmdb_id }}"
    """

    @attr(online=True)
    def test_tmdb_lookup(self):
        self.execute_task('test')
        # check that these were created
        assert self.task.find_entry(tmdb_name='Taken', tmdb_year=2009), 'Didn\'t populate tmdb info for Taken'
        assert self.task.find_entry(tmdb_name='The Matrix', tmdb_year=1999), \
                'Didn\'t populate tmdb info for The Matrix'
