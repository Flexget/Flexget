from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestSeriesPremiere(FlexGetBase):

    __yaml__ = """

        presets:
          global: # just cleans log a bit ..
            disable_builtins:
              - seen

        tasks:
          test_only_one:
            mock:
              - title: Foo's.&.Bar's.2009.S01E01.HDTV.XviD-2HD[FlexGet]
              - title: Foos and Bars 2009 S01E01 HDTV XviD-2HD[ASDF]
              - title: Foo's &amp; Bars (2009) S01E01 720p XviD-2HD[AOEU]
              - title: Foos&bars-2009-S01E01 1080p x264

              - title: Foos and Bars 2009 S01E02 HDTV Xvid-2HD[AOEU]
            series_premiere: yes

          test_dupes_across_tasks_1:
            mock:
              - {title: 'Foo.Bar.2009.S01E01.HDTV.XviD-2HD[FlexGet]'}
            series_premiere: yes

          test_dupes_across_tasks_2:
            mock:
              - {title: 'foo bar (2009) s01e01 dsr xvid-2hd[dmg]'}
            series_premiere: yes
          test_path_set:
            mock:
              - {title: 'foo bar s01e01 hdtv'}
            series_premiere:
              path: .
          test_pilot_and_premiere:
            mock:
              - {title: 'foo bar s01e00 hdtv'}
              - {title: 'foo bar s01e01 hdtv'}
            series_premiere: yes
          test_multi_episode:
            mock:
              - {title: 'foo bar s01e01e02 hdtv'}
            series_premiere: yes
          test_rerun:
            mock:
              - title: theshow s01e01
              - title: theshow s01e02
            series_premiere: yes
            rerun: yes
          test_no_configured_1:
            series:
            - explicit show
          test_no_configured_2:
            series_premiere: yes
            mock:
            - title: explicit show s01e01
            - title: other show s01e01
    """

    def test_only_one(self):
        self.execute_task('test_only_one')
        assert len(self.task.accepted) == 1, 'should only have accepted one'
        assert not self.task.find_entry('accepted', title='Foos and Bars 2009 S01E02 HDTV Xvid-2HD[AOEU]'), \
            'Non premiere accepted'

    def test_dupes_across_tasks(self):
        self.execute_task('test_dupes_across_tasks_1')
        assert len(self.task.accepted) == 1, 'didn\'t accept first premiere'
        self.execute_task('test_dupes_across_tasks_2')
        assert len(self.task.accepted) == 0, 'accepted duplicate premiere'

    def test_path_set(self):
        self.execute_task('test_path_set')
        assert self.task.find_entry(title='foo bar s01e01 hdtv', path='.')

    def test_pilot_and_premiere(self):
        self.execute_task('test_pilot_and_premiere')
        assert len(self.task.accepted) == 2, 'should have accepted pilot and premiere'

    def test_multi_episode(self):
        self.execute_task('test_multi_episode')
        assert len(self.task.accepted) == 1, 'should have accepted multi-episode premiere'

    def test_rerun(self):
        self.execute_task('test_rerun')
        assert not self.task.find_entry('accepted', title='theshow s01e02'), 'accepted non-premiere'

    def test_no_configured_shows(self):
        self.execute_task('test_no_configured_1')
        self.execute_task('test_no_configured_2')
        entry = self.task.find_entry(title='explicit show s01e01')
        assert not entry.accepted
        entry = self.task.find_entry(title='other show s01e01')
        assert entry.accepted