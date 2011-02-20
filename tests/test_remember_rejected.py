from tests import FlexGetBase


class TestRememberRejected(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
    """

    def test_remember_rejected(self):
        self.execute_feed('test')
        entry = self.feed.find_entry(title='title 1')
        self.feed.reject(entry, remember=True)
        self.execute_feed('test')
        assert self.feed.find_entry('rejected', title='title 1', rejected_by='remember_rejected'),\
            'remember_rejected should have rejected'
