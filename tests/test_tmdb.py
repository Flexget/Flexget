import pytest

from flexget.components.tmdb.api_tmdb import TMDBSearchResult
from flexget.manager import Session


@pytest.mark.online
class TestTmdbLookup:
    config = """
        tasks:
          test:
            mock:
              - {title: '[Group] Taken 720p', imdb_url: 'http://www.imdb.com/title/tt0936501/'}
              - {title: 'The Matrix'}
            tmdb_lookup: yes
    """

    def test_tmdb_lookup(self, execute_task):
        task = execute_task('test')
        # check that these were created
        assert task.find_entry(tmdb_name='Taken', tmdb_year=2008), (
            'Didn\'t populate tmdb info for Taken'
        )
        assert task.find_entry(tmdb_name='The Matrix', tmdb_year=1999), (
            'Didn\'t populate tmdb info for The Matrix'
        )


@pytest.mark.online
class TestTmdbUnicodeLookup:
    config = """
        templates:
          global:
            tmdb_lookup: yes
        tasks:
          test_unicode:
            disable: seen
            mock:
                - {'title': '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008', 'url': 'mock://whatever'}
            if:
                - tmdb_year > now.year - 1: reject
    """

    @pytest.mark.xfail(reason='VCR attempts to compare str to unicode')
    def test_unicode(self, execute_task):
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TMDBSearchResult).all()
            assert len(r) == 1, 'Should have added a search result'
            assert r[0].search == '\u0437\u0435\u0440\u043a\u0430\u043b\u0430 mirrors (2008)', (
                'The search result should be lower case'
            )
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TMDBSearchResult).all()
            assert len(r) == 1, 'Should not have added a new row'
