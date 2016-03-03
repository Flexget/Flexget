from __future__ import unicode_literals, division, absolute_import


class TestTmdbLookup(object):

    config = """
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

    def test_tmdb_lookup(self, execute_task, use_vcr):
        task = execute_task('test')
        # check that these were created
        assert task.find_entry(tmdb_name='Taken', tmdb_year=2008), 'Didn\'t populate tmdb info for Taken'
        assert task.find_entry(tmdb_name='The Matrix', tmdb_year=1999), \
                'Didn\'t populate tmdb info for The Matrix'
