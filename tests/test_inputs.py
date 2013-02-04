from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestInputs(FlexGetBase):

    __yaml__ = """
        tasks:
          test_inputs:
            inputs:
              - mock:
                  - {title: 'title1', url: 'http://url1'}
              - mock:
                  - {title: 'title2', url: 'http://url2'}
          test_no_dupes:
            inputs:
              - mock:
                  - {title: 'title1a', url: 'http://url1'}
                  - {title: 'title2', url: 'http://url2a'}
              - mock:
                  - {title: 'title1b', url: 'http://url1'}
                  - {title: 'title1c', url: 'http://other', urls: ['http://url1']}
                  - {title: 'title2', url: 'http://url2b'}
          test_no_url:
            inputs:
              - mock:
                  - title: title1
              - mock:
                  - title: title2
    """

    def test_inputs(self):
        self.execute_task('test_inputs')
        assert len(self.task.entries) == 2, 'Should have created 2 entries'

    def test_no_dupes(self):
        self.execute_task('test_no_dupes')
        assert len(self.task.entries) == 2, 'Should only have created 2 entries'
        assert self.task.find_entry(title='title1a'), 'title1a should be in entries'
        assert self.task.find_entry(title='title2'), 'title2 should be in entries'

    """def test_no_url(self):
        # Oops, this test doesn't do anything, as the mock plugin adds a fake url to entries
        # TODO: fix this
        self.execute_task('test_no_url')
        assert len(self.task.entries) == 2, 'Should have created 2 entries'"""
