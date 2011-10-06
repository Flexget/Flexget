from tests import FlexGetBase


class TestOnlyfeed(FlexGetBase):
    """
        Test --feed option
    """

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'download', url: 'http://localhost/download'}
          test2:
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    def test_manual_with_onlyfeed(self):
        # Pretend we have been run with --feed test
        self.manager.options.onlyfeed = 'test'
        # --feed plugin uses manager.feeds, so we must create it for this test.
        self.manager.create_feeds()
        # This feed should run normally, as we specified it as onlyfeed
        self.execute_feed('test')
        assert self.feed.find_entry(title='download'), \
                'feed failed to download with --feed'
        # This feed should be disabled, as it wasn't specified with onlyfeed
        self.execute_feed('test2')
        assert not self.feed.find_entry(title='nodownload'), \
                'feed should not have been executed'
        # Revert manager settings back to default
        self.manager.options.onlyfeed = None
        self.manager.feeds = {}


class TestManualAutomatic(FlexGetBase):
    """
        Test manual download feeds
    """

    __yaml__ = """
        feeds:
          test:
            manual: true
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    def test_manual_without_onlyfeed(self):
        self.execute_feed('test')
        assert not self.feed.find_entry(title='nodownload'), \
                'Manual feeds downloaded on automatic run'


class TestManualOnlyfeed(FlexGetBase):
    """
        Test manual download feeds
    """

    __yaml__ = """
        feeds:
          test2:
            manual: true
            mock:
              - {title: 'download', url: 'http://localhost/download'}
    """

    def test_manual_with_onlyfeed(self):
        # Pretend we have been run with --feed test2
        self.manager.options.onlyfeed = 'test2'
        # --feed plugin uses manager.feeds, so we must create it for this test.
        self.manager.create_feeds()
        self.execute_feed('test2')
        # Revert manager settings back to default
        self.manager.options.onlyfeed = None
        self.manager.feeds = {}
        assert self.feed.find_entry(title='download'), \
                'Manual feeds failed to download on manual run'
