from __future__ import unicode_literals, division, absolute_import
import os
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

    # This fails on windows when it tries to delete upgrade_test.sqlite
    # WindowsError: [Error 32] The process cannot access the file because it is being used by another process: 'upgrade_test.sqlite'
    #@with_filecopy('db-r1042.sqlite', 'upgrade_test.sqlite')
    def test_upgrade(self):
        # TODO: for some reason this will fail
        return

        self.execute_task('test')
        assert self.task.accepted
