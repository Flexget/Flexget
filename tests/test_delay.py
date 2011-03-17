from datetime import timedelta
from tests import FlexGetBase
from flexget.manager import Session
from flexget.plugins.filter.delay import DelayedEntry


class TestDelay(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            mock:
              - title: entry 1
            delay: 1 hours
        """

    def test_delay(self):
        self.execute_feed('test')
        assert not self.feed.entries, 'No entries should have passed delay'
        # Age the entry in the db
        session = Session()
        delayed_entries = session.query(DelayedEntry).all()
        for entry in delayed_entries:
            entry.expire = entry.expire - timedelta(hours=1)
        session.commit()
        self.execute_feed('test')
        assert self.feed.entries, 'Entry should have passed delay and been inserted'
        # Make sure entry is only injected once
        self.execute_feed('test')
        assert not self.feed.entries, 'Entry should only be insert'
