from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestRememberRejected(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
    """

    def test_remember_rejected(self):
        self.execute_task('test')
        entry = self.task.find_entry(title='title 1')
        entry.reject(remember=True)
        self.execute_task('test')
        assert self.task.find_entry('rejected', title='title 1', rejected_by='remember_rejected'),\
            'remember_rejected should have rejected'
