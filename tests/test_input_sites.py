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

    """

    @pytest.mark.skip(reason='Missing a usable urlrewriter for uploadgig?')
    def test_sceper(self, execute_task):
        task = execute_task('test_sceper')
        assert task.entries, 'no entries created / site may be down'

    def test_apple_trailers(self, execute_task, use_vcr):
        task = execute_task('test_apple_trailers')
        assert task.entries, 'no entries created / site may be down'

    def test_apple_trailers_simple(self, execute_task):
        task = execute_task('test_apple_trailers_simple')
        assert task.entries, 'no entries created / site may be down'
