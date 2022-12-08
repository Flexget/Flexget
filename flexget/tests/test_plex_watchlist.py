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
            - {title: 'Avatar: The Way of Water (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt1630029"}
            - {title: 'Avatar: The Way of Water (2022)', url: "http://mock.url/file3.torrent"}
            - {title: 'Some other movie (2022)', url: "http://mock.url/file3.torrent", "imdb_id": "tt123445"}
          list_match:
            from:
              - plex_watchlist:
                  <<: *plex_def
            remove_on_match: no
            single_match: no
    """ % {
        'PLEX_USERNAME': PLEX_USERNAME,
        'PLEX_PASSWORD': PLEX_PASSWORD,
    }

    def test_match(self, execute_task):
        task = execute_task('test_match')
        assert len(task.accepted) == 2
