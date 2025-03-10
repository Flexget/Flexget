from flexget.manager import Session
from flexget.plugins.filter.upgrade import EntryUpgrade


class TestUpgrade:
    config = """
        tasks:
          first_download:
            accept_all: yes
            upgrade:
              tracking: yes
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'media_id': 'Movie'}
          tracking_only:
            upgrade:
              tracking: yes
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'media_id': 'Movie'}
          upgrade_quality:
            upgrade:
              target: 1080p
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'media_id': 'Movie'}
              - {title: 'Movie.720p.WEB-DL.X264.AC3', 'media_id': 'Movie'}
              - {title: 'Movie.BRRip.x264.720p', 'media_id': 'Movie'}
          reject_lower:
            upgrade:
              target: 1080p
              on_lower: reject
            mock:
              - {title: 'Movie.1080p.BRRip.X264.AC3', 'media_id': 'Movie'}
              - {title: 'Movie.1080p WEB-DL X264', 'media_id': 'Movie'}
              - {title: 'Movie.BRRip.x264.720p', 'media_id': 'Movie'}
    """

    def test_learn(self, execute_task):
        execute_task('first_download')
        with Session() as session:
            query = session.query(EntryUpgrade).all()
            assert len(query) == 1, 'There should be one tracked entity present.'
            assert query[0].id == 'movie', 'Should have tracked name `Movie`.'

    def test_tracking(self, execute_task):
        execute_task('first_download')
        task = execute_task('tracking_only')
        entry = task.find_entry('undecided', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should be undecided'

    def test_upgrade_quality(self, execute_task):
        execute_task('first_download')
        task = execute_task('upgrade_quality')
        entry = task.find_entry('accepted', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should have been accepted'

    def test_reject_lower(self, execute_task):
        execute_task('first_download')
        task = execute_task('reject_lower')
        entry = task.find_entry('accepted', title='Movie.1080p.BRRip.X264.AC3')
        assert entry, 'Movie.1080p.BRRip.X264.AC3 should have been accepted'
        entry = task.find_entry('rejected', title='Movie.1080p WEB-DL X264')
        assert entry, 'Movie.1080p WEB-DL X264 should have been rejected'
        entry = task.find_entry('rejected', title='Movie.BRRip.x264.720p')
        assert entry, 'Movie.BRRip.x264.720p should have been rejected'


class TestUpgradeTarget:
    config = """
        tasks:
          existing_download_480p:
            upgrade:
              tracking: yes
            accept_all: yes
            mock:
              - {title: 'Movie.480p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          existing_download_1080p:
            upgrade:
              tracking: yes
            accept_all: yes
            mock:
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          target_outside_range:
            upgrade:
              target: 720p-1080p
            mock:
              - {title: 'Movie.HDRip.XviD.AC3', 'id': 'Movie'}
          target_within_range:
            upgrade:
              target: 720p-1080p
            mock:
              - {title: 'Movie.2160p WEB-DL X264 AC3', 'id': 'Movie'}
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'id': 'Movie'}
              - {title: 'Movie.720p.WEB-DL.X264.AC3', 'id': 'Movie'}
          target_quality_1080p:
            upgrade:
              target: 1080p
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'id': 'Movie'}
              - {title: 'Movie.720p.WEB-DL.X264.AC3', 'id': 'Movie'}
    """

    def test_target_outside_range(self, execute_task):
        execute_task('existing_download_480p')
        task = execute_task('target_outside_range')
        entry = task.find_entry('undecided', title='Movie.HDRip.XviD.AC3')
        assert entry, 'Movie.HDRip.XviD.AC3 should have been undecided'

    def test_target_within_range(self, execute_task):
        execute_task('existing_download_480p')
        task = execute_task('target_within_range')
        entry = task.find_entry('accepted', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should have been accepted'

        for title in ['Movie.2160p WEB-DL X264 AC3', 'Movie.720p.WEB-DL.X264.AC3']:
            entry = task.find_entry('undecided', title=title)
            assert entry, f'{title} should have been undecided'

    def test_target_quality_1080p(self, execute_task):
        execute_task('existing_download_480p')
        task = execute_task('target_quality_1080p')
        entry = task.find_entry('accepted', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should have been accepted'
        entry = task.find_entry('undecided', title='Movie.720p.WEB-DL.X264.AC3')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3 should have been undecided'

    def test_at_target(self, execute_task):
        execute_task('existing_download_1080p')
        task = execute_task('target_quality_1080p')
        entry = task.find_entry('undecided', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.1080p WEB-DL X264 AC3 should have been accepted'
        entry = task.find_entry('undecided', title='Movie.720p.WEB-DL.X264.AC3')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3 should have been undecided'


class TestUpgradeTimeFrame:
    config = """
        tasks:
          existing_download_480p:
            upgrade:
              tracking: yes
            accept_all: yes
            mock:
              - {title: 'Movie.480p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          outside_timeframe:
            upgrade:
              timeframe: 0 seconds
              target: 1080p
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'id': 'Movie'}
          within_timeframe:
            upgrade:
              timeframe: 1 day
              target: 1080p
            mock:
              - {title: 'Movie.1080p WEB-DL X264 AC3', 'id': 'Movie'}
    """

    def test_outside_timeframe(self, execute_task):
        execute_task('existing_download_480p')
        task = execute_task('outside_timeframe')
        entry = task.find_entry('undecided', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.HDRip.XviD.AC3 should have been undecided'

    def test_within_timeframe(self, execute_task):
        execute_task('existing_download_480p')
        task = execute_task('within_timeframe')
        entry = task.find_entry('accepted', title='Movie.1080p WEB-DL X264 AC3')
        assert entry, 'Movie.HDRip.XviD.AC3 should have been accepted'


class TestUpgradePropers:
    config = """
        templates:
          global:
            metainfo_movie: yes
            upgrade:
              target: 1080p
              tracking: yes
              propers: yes
        tasks:
          existing_download:
            accept_all: yes
            mock:
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1'}
          existing_download_proper:
            accept_all: yes
            mock:
              - {title: 'Movie.1080p PROPER WEB-DL X264 AC3 GRP1'}
          existing_download_proper_repack:
            accept_all: yes
            mock:
              - {title: 'Movie.1080p PROPER REPACK WEB-DL X264 AC3 GRP1'}
          upgrade_proper:
            mock:
              - {title: 'Movie.1080p REPACK PROPER WEB-DL X264 AC3'}
              - {title: 'Movie.1080p PROPER WEB-DL X264 AC3'}
          existing_upgrade_proper:
            mock:
              - {title: 'Movie.1080p REPACK PROPER WEB-DL X264 AC3'}
              - {title: 'Movie.1080p PROPER WEB-DL X264 AC3'}
          existing_higher_proper:
            mock:
              - {title: 'Movie.1080p PROPER WEB-DL X264 AC3'}
          existing_lower_quality_proper:
            mock:
              - {title: 'Movie.720p PROPER WEB-DL X264 AC3'}
    """

    def test_upgrade_proper(self, execute_task):
        execute_task('existing_download')
        task = execute_task('upgrade_proper')
        entry = task.find_entry('accepted', title='Movie.1080p REPACK PROPER WEB-DL X264 AC3')
        assert entry, 'Movie.1080p REPACK PROPER WEB-DL X264 AC3 should have been accepted'

    def test_existing_upgrade_proper(self, execute_task):
        execute_task('existing_download_proper')
        task = execute_task('existing_upgrade_proper')
        entry = task.find_entry('accepted', title='Movie.1080p REPACK PROPER WEB-DL X264 AC3')
        assert entry, 'Movie.1080p REPACK PROPER WEB-DL X264 AC3 should have been accepted'

    def test_existing_higher_proper(self, execute_task):
        execute_task('existing_download_proper_repack')
        task = execute_task('existing_higher_proper')
        entry = task.find_entry('undecided', title='Movie.1080p PROPER WEB-DL X264 AC3')
        assert entry, 'Movie.1080p PROPER WEB-DL X264 AC3 should have been undecided'

    def test_existing_lower_quality_proper(self, execute_task):
        execute_task('existing_download')
        task = execute_task('existing_lower_quality_proper')
        entry = task.find_entry('undecided', title='Movie.720p PROPER WEB-DL X264 AC3')
        assert entry, 'Movie.720p PROPER WEB-DL X264 AC3 should have been undecided'
