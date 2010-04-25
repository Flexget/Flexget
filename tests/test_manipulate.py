from tests import FlexGetBase


class TestManipulate(FlexGetBase):

    __yaml__ = """
        feeds:
          test_1:
            mock:
              - {title: 'abc FOO'}
            manipulate:
              title:
                replace:
                  regexp: FOO
                  format: BAR
          test_2:
            mock:
              - {title: '1234 abc'}
            manipulate:
              title:
                extract: \d+(.*)
    """

    def test_replace(self):
        self.execute_feed('test_1')
        assert self.feed.find_entry('entries', title='abc BAR'), 'replace failed'

    def test_extract(self):
        self.execute_feed('test_2')
        assert self.feed.find_entry('entries', title='abc'), 'extract failed'
