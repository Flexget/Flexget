from tests import FlexGetBase

class TestTorrentSize(FlexGetBase):
    __yaml__ = """
        global:
          input_mock:
            - {title: 'test', file: 'tests/test.torrent'}
          disable_builtins:
            - seen

        feeds:
          test_min:
            torrent_size:
              min: 2000

          test_max:
            torrent_size:
              max: 10
              
          test_strict:
            preset:
              - no_global
            input_mock:
              - {title: 'test'}
            torrent_size:
              min: 1
              strict: yes
    """

    def test_min(self):
        self.execute_feed('test_min')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, minimum size'

    def test_max(self):
        self.execute_feed('test_max')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, maximum size'
            
    def test_strict(self):
        self.execute_feed('test_strict')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected non torrent'
            
