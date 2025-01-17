import datetime

from flexget.manager import Session
from flexget.plugins.filter.timeframe import EntryTimeFrame


def age_timeframe(**kwargs):
    with Session() as session:
        session.query(EntryTimeFrame).update(
            {'first_seen': datetime.datetime.now() - datetime.timedelta(**kwargs)}
        )


class TestTimeFrame:
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          wait:
            timeframe:
              wait: 1 day
              target: 1080p
            mock:
              - {title: 'Movie.BRRip.x264.720p', 'media_id': 'Movie'}
              - {title: 'Movie.720p WEB-DL X264 AC3', 'media_id': 'Movie'}
          reached_and_backlog:
            timeframe:
              wait: 1 hour
              target: 1080p
              on_reached: accept
            mock:
              - {title: 'Movie.720p WEB-DL X264 AC3', 'media_id': 'Movie'}
              - {title: 'Movie.BRRip.x264.720p', 'media_id': 'Movie'}
          target1:
            timeframe:
              wait: 1 hour
              target: 1080p
              on_reached: accept
            mock:
              - {title: 'Movie.720p WEB-DL X264 AC3', 'media_id': 'Movie'}
              - {title: 'Movie.BRRip.x264.720p', 'media_id': 'Movie'}
          target2:
            timeframe:
              wait: 1 hour
              target: 1080p
              on_reached: accept
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'media_id': 'Movie'}
    """

    def test_wait(self, execute_task):
        task = execute_task('wait')
        with Session() as session:
            query = session.query(EntryTimeFrame).all()
            assert len(query) == 1, 'There should be one tracked entity present.'
            assert query[0].id == 'movie', 'Should have tracked name `Movie`.'

        entry = task.find_entry('rejected', title='Movie.BRRip.x264.720p')
        assert entry, 'Movie.BRRip.x264.720p should be rejected'
        entry = task.find_entry('rejected', title='Movie.720p WEB-DL X264 AC3')
        assert entry, 'Movie.720p WEB-DL X264 AC3 should be rejected'

    def test_reached_and_backlog(self, manager, execute_task):
        execute_task('reached_and_backlog')
        age_timeframe(hours=1)

        # simulate movie going away from the task/feed
        del manager.config['tasks']['reached_and_backlog']['mock']

        task = execute_task('reached_and_backlog')
        entry = task.find_entry('accepted', title='Movie.BRRip.x264.720p')
        assert entry, 'Movie.BRRip.x264.720p should be accepted, backlog not injecting'

    def test_target(self, execute_task):
        execute_task('target1')
        task = execute_task('target2')
        entry = task.find_entry('accepted', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should be undecided'

    def test_learn(self, execute_task):
        execute_task('target2')
        with Session() as session:
            query = session.query(EntryTimeFrame).all()
            assert len(query) == 1, 'There should be one tracked entity present.'
            assert query[0].status == 'accepted', 'Should be accepted.'


class TestTimeFrameActions:
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          wait_reject:
            timeframe:
              wait: 1 day
              target: 1080p
              on_waiting: reject
            mock:
              - {title: 'Movie.BRRip.x264.720p', 'id': 'Movie'}
              - {title: 'Movie.720p WEB-DL X264 AC3', 'id': 'Movie'}
          reached_accept:
            timeframe:
              wait: 1 hour
              target: 1080p
              on_reached: accept
            mock:
              - {title: 'Movie.720p WEB-DL X264 AC3', 'id': 'Movie'}
              - {title: 'Movie.BRRip.x264.720p', 'id': 'Movie'}
    """

    def test_on_reject(self, execute_task):
        task = execute_task('wait_reject')
        entry = task.find_entry('rejected', title='Movie.BRRip.x264.720p')
        assert entry, 'Movie.BRRip.x264.720p should be rejected'
        entry = task.find_entry('rejected', title='Movie.720p WEB-DL X264 AC3')
        assert entry, 'Movie.720p WEB-DL X264 AC3 should be rejected'

    def test_on_reached(self, manager, execute_task):
        execute_task('reached_accept')
        age_timeframe(hours=1)
        task = execute_task('reached_accept')
        entry = task.find_entry('accepted', title='Movie.BRRip.x264.720p')
        assert entry, 'Movie.BRRip.x264.720p should be undecided, backlog not injecting'
