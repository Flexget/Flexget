import pytest

from .conftest import MockManager


class TestMigrate:
    config = """
        tasks:
          test:
            mock:
              - {title: 'foobar'}
            accept_all: yes
    """

    @pytest.mark.filecopy("db-r1042.sqlite", "__tmp__/upgrade_test.sqlite")
    def test_upgrade(self, request, tmp_path):
        filename = tmp_path / "upgrade_test.sqlite"
        database_uri = f"sqlite:///{filename}"
        # This will raise an error if the upgrade wasn't successful
        mockmanager = MockManager(
            self.config, request.cls.__name__, db_uri=database_uri, tmp_path=tmp_path
        )
        mockmanager.shutdown()
        # TODO: verify we actually loaded the old config, and didn't just create a new one or something
