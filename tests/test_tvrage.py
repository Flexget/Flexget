from tests import FlexGetBase
from flexget.plugins.api_tvrage import lookup_series
import logging

log = logging.getLogger('TestTvRage')

class TestTvRage(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'irrelevant'}
    """

    def test_setdefault(self):
        log.info("runninnngggg")
        show = lookup_series("Friends")
        s1 = show.season(1)
        assert s1
        log.info("s1 %s " % s1)
        s31 = show.season(31)
        assert not s31
        log.info("s31 %s " % s31)
        e1 = s1.episode(1)
        assert e1
        log.info("e1 %s " % e1)
        e32 = s1.episode(32)
        log.info("e32 %s " % e32)
        assert not e32
        