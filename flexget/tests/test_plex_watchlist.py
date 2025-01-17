import pytest

PLEX_USERNAME = 'flexget_flexget'
PLEX_PASSWORD = 'flexget_flexget'


@pytest.mark.online
class TestPlex:
    config = f"""
      templates:
        global:
          disable: [seen]
        settings:
          _plex: &plex_def
            username: "{PLEX_USERNAME}"
            password: {PLEX_PASSWORD}
      tasks:
        plex_watchlist:
          plex_watchlist:
            <<: *plex_def
          accept_all: true
        test_list_add:
          mock:
            - {{title: 'Amsterdam (2022)', url: "http://mock.url/file3.torrent"}}
            - {{title: 'Black Adam (2022)', url: "http://mock.url/file3.torrent", "plex_guid": "plex://movie/5d776ca79ab544002151945c"}}
            - {{title: 'Avatar: The Way of Water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}}
            - {{title: 'Some non matchable movie (2022)', url: "http://mock.url/file3.torrent"}}
          metainfo_movie: true
          accept_all: true
          list_add:
            - plex_watchlist:
                <<: *plex_def
        test_list_match:
          mock:
            - {{title: 'Amsterdam (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt10304142"}}
            - {{title: 'Black Adam (2022)', url: "http://mock.url/file3.torrent"}}
            - {{title: 'Avatar: The Way of Water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}}
            - {{title: 'Some other movie (2022)', url: "http://mock.url/file3.torrent"}}
          list_match:
            from:
              - plex_watchlist:
                  <<: *plex_def
            remove_on_match: no
            single_match: no
        test_list_remove:
          mock:
            - {{title: 'Some other movie (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt123445"}}
            - {{title: 'Black Adam (2022)', url: "http://mock.url/file3.torrent", "plex_guid": "plex://movie/5d776ca79ab544002151945c"}}
            - {{title: 'Avatar: The Way of Water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}}
          accept_all: true
          list_remove:
            - plex_watchlist:
                <<: *plex_def
    """

    def test_list_add(self, execute_task):
        task = execute_task('test_list_add')
        task = execute_task('plex_watchlist')
        assert len(task.entries) == 3

    def test_list_match(self, execute_task):
        task = execute_task('test_list_match')
        assert len(task.accepted) == 3

    def test_list_remove(self, execute_task):
        task = execute_task('test_list_remove')
        task = execute_task('plex_watchlist')
        assert len(task.entries) == 1
