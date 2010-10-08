from tests import FlexGetBase


class TestUrlfix(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Test', url: 'http://localhost/foo?bar=asdf&amp;xxx=yyy'}
          test2:
            mock:
              - {title: 'Test', url: 'http://localhost/foo?bar=asdf&amp;xxx=yyy'}
            urlfix: no
    """

    def test_urlfix(self):
        self.execute_feed('test')
        entry = self.feed.find_entry('entries', title='Test')
        assert entry['url'] == 'http://localhost/foo?bar=asdf&xxx=yyy', \
            'failed to auto fix url, got %s' % entry['url']

    def test_urlfix_disabled(self):
        self.execute_feed('test2')
        entry = self.feed.find_entry('entries', title='Test')
        assert entry['url'] != 'http://localhost/foo?bar=asdf&xxx=yyy', \
            'fixed even when disabled, got %s' % entry['url']
