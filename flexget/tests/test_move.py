import pytest


@pytest.mark.usefixtures('tmpdir')
class TestMove:
    config = """
        tasks:
          test_move:
            mock:
            - title: a movie
              location: __tmp__/movie.mkv
            accept_all: yes
            move:
              # Take advantage that path validation allows non-existent dirs if they are jinja
              to: __tmp__/{{ 'newdir' }}/
    """

    @pytest.mark.filecopy('movie.mkv', '__tmp__/movie.mkv')
    def test_move(self, execute_task, tmpdir):
        assert (tmpdir / 'movie.mkv').exists()
        task = execute_task('test_move')
        assert not (tmpdir / 'movie.mkv').exists()
        assert (tmpdir / 'newdir/movie.mkv').exists()
