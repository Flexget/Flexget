from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestSimplePersistence(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'irrelevant'}
    """

    def test_setdefault(self):
        self.execute_task('test')

        task = self.task

        value1 = task.simple_persistence.setdefault('test', 'abc')
        value2 = task.simple_persistence.setdefault('test', 'def')

        assert value1 == value2, 'set default broken'
