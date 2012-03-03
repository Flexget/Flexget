from tests import FlexGetBase


class TestManipulate(FlexGetBase):

    __yaml__ = """
        feeds:

          test_1:
            mock:
              - {title: 'abc FOO'}
            manipulate:
              - title:
                  replace:
                    regexp: FOO
                    format: BAR

          test_2:
            mock:
              - {title: '1234 abc'}
            manipulate:
              - title:
                  extract: \d+\s*(.*)

          test_multiple_edits:
            mock:
              - {title: 'abc def'}
            manipulate:
              - title:
                  replace:
                    regexp: abc
                    format: "123"
              - title:
                  extract: \d+\s+(.*)

          test_phase:
            mock:
              - {title: '1234 abc'}
            manipulate:
              - title:
                  phase: metainfo
                  extract: \d+\s*(.*)
    """

    def test_replace(self):
        self.execute_feed('test_1')
        assert self.feed.find_entry('entries', title='abc BAR'), 'replace failed'

    def test_extract(self):
        self.execute_feed('test_2')
        assert self.feed.find_entry('entries', title='abc'), 'extract failed'

    def test_multiple_edits(self):
        self.execute_feed('test_multiple_edits')
        assert self.feed.find_entry('entries', title='def'), 'multiple edits on 1 field failed'

    def test_phase(self):
        self.execute_feed('test_phase')
        assert self.feed.find_entry('entries', title='abc'), 'extract failed at metainfo phase'
