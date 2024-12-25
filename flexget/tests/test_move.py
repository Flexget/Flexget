import pytest


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
    def test_move(self, execute_task, tmp_path):
        assert tmp_path.joinpath('movie.mkv').exists()
        execute_task('test_move')
        assert not tmp_path.joinpath('movie.mkv').exists()
        assert tmp_path.joinpath('newdir/movie.mkv').exists()
