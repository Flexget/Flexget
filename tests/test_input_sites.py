import pytest


@pytest.mark.online
class TestInputSites:
    config = """
        templates:
          global:
            headers:
              User-Agent: >-
                Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36
                (KHTML, like Gecko) Chrome/35.0.1916.114 Safari/537.36
        tasks:
          test_sceper:
            sceper: http://sceper.ws/category/movies/movies-dvd-rip
          test_apple_trailers:
            apple_trailers:
              quality: 480p
              genres: ['Action and Adventure']
          test_apple_trailers_simple:
            apple_trailers: 720p
          test_from_piratebay_all:
            from_piratebay:
              list: top
          test_from_piratebay_cat:
            from_piratebay:
              category: HD - Movies
          test_from_piratebay_all_48h:
            from_piratebay:
              list: top48h
          test_from_piratebay_cat_48h:
            from_piratebay:
              category: HD - Movies
              list: top48h
          test_from_piratebay_rank:
            from_piratebay:
              rank: supermod
          test_from_piratebay_query:
            from_piratebay:
              query: user:metheguy
    """

    @pytest.mark.skip(reason='Missing a usable urlrewriter for uploadgig?')
    def test_sceper(self, execute_task):
        task = execute_task('test_sceper')
        assert task.entries, 'no entries created / site may be down'

    def test_apple_trailers(self, execute_task):
        task = execute_task('test_apple_trailers')
        assert task.entries, 'no entries created / site may be down'

    def test_apple_trailers_simple(self, execute_task):
        task = execute_task('test_apple_trailers_simple')
        assert task.entries, 'no entries created / site may be down'

    def test_from_piratebay_all(self, execute_task):
        task = execute_task('test_from_piratebay_all')
        assert task.entries, 'no entries created / site may be down'

    def test_from_piratebay_cat(self, execute_task):
        task = execute_task('test_from_piratebay_cat')
        assert task.entries, 'no entries created / site may be down'

    def test_from_piratebay_all_48h(self, execute_task):
        task = execute_task('test_from_piratebay_all_48h')
        assert task.entries, 'no entries created / site may be down'

    def test_from_piratebay_cat_48h(self, execute_task):
        task = execute_task('test_from_piratebay_cat_48h')
        assert task.entries, 'no entries created / site may be down'

    def test_from_piratebay_rank(self, execute_task):
        # unlikely to return entries
        execute_task('test_from_piratebay_rank')

    def test_from_piratebay_query(self, execute_task):
        # unlikely to return entries
        execute_task('test_from_piratebay_query')
