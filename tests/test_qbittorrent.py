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
          seeding_time_limit:
            qbittorrent:
              seeding_time_limit: 1 day
          inactive_seeding_time_limit:
            qbittorrent:
              inactive_seeding_time_limit: 3 weeks
          incomplete_path:
            qbittorrent:
              incomplete_path: /tmp
          api_key:
            qbittorrent:
              api_key: qbt_FlexGetTestKey0000000000000
          wrong_api_key:
            qbittorrent:
              api_key: qbt_WrongKey00000000000000000000
          from_qbittorrent_api_key:
            template: no
            from_qbittorrent:
              host: localhost
              port: 8080
              api_key: qbt_FlexGetTestKey0000000000000
        """

    def test_default(self, execute_task):
        task = execute_task('default')
        assert task.accepted

    def test_ratio_limit(self, execute_task):
        task = execute_task('ratio_limit')
        assert task.accepted

    def test_seeding_time_limit(self, execute_task):
        task = execute_task('seeding_time_limit')
        assert task.accepted

    def test_inactive_seeding_time_limit(self, execute_task):
        task = execute_task('inactive_seeding_time_limit')
        assert task.accepted

    def test_incomplete_path(self, execute_task):
        task = execute_task('incomplete_path')
        assert task.accepted

    def test_api_key(self, execute_task, use_vcr):
        task = execute_task('api_key')
        assert task.accepted
        if use_vcr:
            assert all(
                r.headers.get('Authorization') == 'Bearer qbt_FlexGetTestKey0000000000000'
                for r in use_vcr.requests
            )
            assert not any(r.path.endswith('/auth/login') for r in use_vcr.requests)

    def test_wrong_api_key(self, execute_task):
        execute_task('wrong_api_key', abort=True)

    def test_from_qbittorrent_api_key(self, execute_task):
        task = execute_task('from_qbittorrent_api_key')
        assert task.all_entries
