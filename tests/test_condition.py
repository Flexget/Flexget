import logging
from tests import FlexGetBase

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
            mock:
              - {title: 'test', year: 2000}
              - {title: 'brilliant', rating: 9.9}
              - {title: 'fresh', year: 2011}

        feeds:
          test_reject:
            reject_if: year<2011
          test_accept:
            accept_if:
              - year>=2010
              - rating>9
    """

    def test_reject(self):
        if pyrocore:
            self.execute_feed('test_reject')
            count = len(self.feed.rejected) 
            assert count == 1

    def test_accept(self):
        if pyrocore:
            self.execute_feed('test_accept')
            count = len(self.feed.accepted)
            assert count == 2
