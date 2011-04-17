from tests import FlexGetBase


class TestInputs(FlexGetBase):

    __yaml__ = """
        feeds:
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
    """

    def test_inputs(self):
        self.execute_feed('test_inputs')
        assert len(self.feed.entries) == 2, 'Should have created 2 entries'

    def test_no_dupes(self):
        self.execute_feed('test_no_dupes')
        assert len(self.feed.entries) == 2, 'Should only have created 2 entries'
        assert self.feed.find_entry(title='title1a'), 'title1a should be in entries'
        assert self.feed.find_entry(title='title2'), 'title2 should be in entries'
