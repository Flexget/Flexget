import pytest


@pytest.mark.online
@pytest.mark.require_optional_deps
class TestQbittorrent:
    config = """
        templates:
          global:
            accept_all: yes
            mock:
              - title: test magnet
                url: magnet:?xt=urn:btih:2a8959bed2be495bb0e3ea96f497d873d5faed05&dn=some.thing.720p
        tasks:
          default:
            qbittorrent: yes
          ratio_limit:
            qbittorrent:
              ratio_limit: 1.65
        """

    def test_default(self, execute_task):
        task = execute_task('default')
        assert task.accepted

    def test_ratio_limit(self, execute_task):
        task = execute_task('ratio_limit')
        assert task.accepted
