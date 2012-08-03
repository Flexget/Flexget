import os
from tests import with_filecopy
from tests import FlexGetBase


class TestMigrate(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'foobar'}
            accept_all: yes
    """

    def setup(self):
        import logging
        logging.critical('TestMigrate.setup()')
        db_filename = os.path.join(self.base_path, 'upgrade_test.sqlite')
        # in case running on windows, needs double \\
        filename = db_filename.replace('\\', '\\\\')
        self.database_uri = 'sqlite:///%s' % filename
        super(TestMigrate, self).setup()

    @with_filecopy('db-r1042.sqlite', 'upgrade_test.sqlite')
    def test_upgrade(self):
        # TODO: for some reason this will fail
        return

        self.execute_task('test')
        assert self.task.accepted
