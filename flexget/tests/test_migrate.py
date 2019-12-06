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

    @pytest.mark.filecopy('db-r1042.sqlite', '__tmp__/upgrade_test.sqlite')
    def test_upgrade(self, request, tmpdir):
        db_filename = tmpdir.join('upgrade_test.sqlite')
        # in case running on windows, needs double \\
        filename = db_filename.strpath.replace('\\', '\\\\')
        database_uri = 'sqlite:///%s' % filename
        # This will raise an error if the upgrade wasn't successful
        mockmanager = MockManager(self.config, request.cls.__name__, db_uri=database_uri)
        mockmanager.shutdown()
        # TODO: verify we actually loaded the old config, and didn't just create a new one or something
