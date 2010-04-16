import os
from tests import FlexGetBase
from nose.plugins.attrib import attr
from nose.tools import raises
from flexget.feed import EntryUnicodeError, Entry


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
        self.manager.options.onlyfeed = 'test2'
        self.execute_feed('test2')
        assert self.feed.find_entry(title='download'), \
                'Manual feeds failed to download on manual run'
