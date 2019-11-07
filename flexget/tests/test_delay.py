from datetime import timedelta

from flexget.manager import Session
from flexget.plugins.filter.delay import DelayedEntry


class TestDelay:
    config = """
        tasks:
          test:
            mock:
              - title: entry 1
            delay: 1 hours
        """

    def test_delay(self, execute_task):
        task = execute_task('test')
        assert not task.entries, 'No entries should have passed delay'
        # Age the entry in the db
        session = Session()
        delayed_entries = session.query(DelayedEntry).all()
        for entry in delayed_entries:
            entry.expire = entry.expire - timedelta(hours=1)
        session.commit()
        task = execute_task('test')
        assert task.entries, 'Entry should have passed delay and been inserted'
        # Make sure entry is only injected once
        task = execute_task('test')
        assert not task.entries, 'Entry should only be insert'
