import pytest

PLEX_USERNAME = 'flexget_flexget'
PLEX_PASSWORD = 'flexget_flexget'


@pytest.mark.online
class TestPlex:
    config = """
      templates:
        settings:
          _plex: &plex_def
            username: "%(PLEX_USERNAME)s"
            password: %(PLEX_PASSWORD)s
      tasks:
        test_match:
          mock:
            - {title: 'Avatar the way of the water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}
          list_match:
            from:
              - plex_watchlist:
                  <<: *plex_def
            remove_on_match: no
        test_no_match:
          mock:
            - {title: 'Avatar the way of the water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}
          list_match:
            from:
              - plex_watchlist:
                  <<: *plex_def
            remove_on_match: no
    """ % {
        'PLEX_USERNAME': PLEX_USERNAME,
        'PLEX_PASSWORD': PLEX_PASSWORD,
    }

    def test_match(self, execute_task):
        task = execute_task('test_match')
        assert len(task.accepted) == 1
        task = execute_task('test_no_match')
        assert len(task.accepted) == 0
