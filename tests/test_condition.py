import logging
from tests import FlexGetBase, with_filecopy

log = logging.getLogger(__name__)

try:
    import pyrocore
except ImportError:
    log.warning("Condition tests disabled (pyrocore>=0.4 not installed)")
    pyrocore = None


class TestCondition(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            disable_builtins: [seen]
            mock:
              - {title: 'test', year: 2000}
              - {title: 'brilliant', rating: 9.9}
              - {title: 'fresh', year: 2011}

        feeds:
          test_condition_reject:
            reject_if: year<2011

          test_condition_accept:
            accept_if:
              - ?year>=2010
              - ?rating>9

          test_condition_and1:
            accept_if: '*t ?rating>9'
          test_condition_and2:
            accept_if: '*t'
    """

    def test_reject(self):
        if pyrocore:
            self.execute_feed('test_condition_reject')
            count = len(self.feed.rejected) 
            assert count == 1

    def test_accept(self):
        if pyrocore:
            self.execute_feed('test_condition_accept')
            count = len(self.feed.accepted)
            assert count == 2

    def test_implicit_and(self):
        if pyrocore:
            for i in "12":
                self.execute_feed('test_condition_and' + i)
                count = len(self.feed.accepted)
                assert count == int(i)


class TestDownloadCondition(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            disable_builtins: [seen]
            mock:
              - {title: 'test', file: 'test.torrent'}
              - {title: 'prv', file: 'private.torrent'}
              - {title: 'not_a_torrent'}

        feeds:
          test_condition_field_access1:
            reject_if_download: ?torrent.content.info.?private=1

          test_condition_field_access2:
            reject_if_download: ?torrent.content.announce=*ubuntu.com[/:]*
    """

    def test_field_access(self):
        if pyrocore:
            for i in "12":
                self.execute_feed('test_condition_field_access' + i)
                count = len(self.feed.rejected)
                assert count == int(i), "Expected %s rejects, got %d" % (i, count)
                assert i != "1" or self.feed.rejected[0]["title"] == "prv"
