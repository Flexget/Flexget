import pytest

from flexget.components.managed_lists.lists.imdb_list import ImdbEntrySet


@pytest.mark.skip(reason="It rarely works")
@pytest.mark.online
class TestIMDBListTypes:
    imdb_config = {
        'login': 'siysbijz@sharklasers.com',
        'password': 'flexget16',
        'list': 'watchlist',
    }

    config = """
        tasks:
          imdb_list_add:
            mock:
              - {title: 'the matrix', url: 'http://localhost/seen1', imdb_id: 'tt0133093'}
              - {title: 'black mirror', url: 'http://localhost/seen2', imdb_id: 'tt2085059'}
              - {title: 'blackfish', url: 'http://localhost/seen3', imdb_id: 'tt2545118'}
            accept_all: yes
            list_add:
              - imdb_list:
                  login: 'siysbijz@sharklasers.com'
                  password: 'flexget16'
                  list: 'watchlist'

          imdb_list_get:
            imdb_list:
              login: 'siysbijz@sharklasers.com'
              password: 'flexget16'
              list: 'watchlist'
            accept_all: yes

          imdb_list_remove:
            imdb_list:
              login: 'siysbijz@sharklasers.com'
              password: 'flexget16'
              list: 'watchlist'
            accept_all: yes
            list_remove:
              - imdb_list:
                  login: 'siysbijz@sharklasers.com'
                  password: 'flexget16'
                  list: 'watchlist'
    """

    def test_imdb_list(self, execute_task):
        imdb_set = ImdbEntrySet(self.imdb_config)
        # Clearing existing list
        imdb_set.clear()

        task = execute_task('imdb_list_add')
        assert len(task.accepted) == 3

        task = execute_task('imdb_list_get')
        assert len(task.accepted) == 3
        assert task.find_entry(movie_name='The Matrix', movie_year=1999)
        assert task.find_entry(series_name='Black Mirror', series_year=2011)
        assert task.find_entry(movie_name='Blackfish', movie_year=2013)

        task = execute_task('imdb_list_remove')
        assert len(task.all_entries) == 3

        task = execute_task('imdb_list_get')
        assert len(task.accepted) == 0
