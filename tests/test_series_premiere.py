import pytest
from jinja2 import Template


@pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
def config(request):
    """Override and parametrize default config fixture for all series tests."""
    return Template(request.cls.config).render({'parser': request.param})


class TestSeriesPremiere:
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            disable: [seen]  # just cleans log a bit ..

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
          test_no_teasers:
            mock:
              - {title: 'foo bar s01e00 hdtv'}
              - {title: 'foo bar s01e01 hdtv'}
            series_premiere:
              allow_teasers: no
          test_multi_episode:
            mock:
              - {title: 'foo bar s01e01e02 hdtv'}
            series_premiere: yes
          test_rerun:
            mock:
              - title: theshow s01e01
              - title: theshow s01e02
            series_premiere: yes
            rerun: 1
          test_no_rerun_with_series:
            mock:
              - title: theshow s01e01
              - title: theshow s01e02
            series_premiere: yes
            series:
              - theshow
            rerun: 0
          test_no_rerun:
            mock:
              - title: theshow s01e01
              - title: theshow s01e02
            series_premiere: yes
            rerun: 0
          test_no_configured_1:
            series:
            - explicit show
          test_no_configured_2:
            series_premiere: yes
            mock:
            - title: explicit show s01e01
            - title: other show s01e01
    """

    def test_only_one(self, execute_task):
        task = execute_task('test_only_one')
        assert len(task.accepted) == 1, 'should only have accepted one'
        assert not task.find_entry(
            'accepted', title='Foos and Bars 2009 S01E02 HDTV Xvid-2HD[AOEU]'
        ), 'Non premiere accepted'

    def test_dupes_across_tasks(self, execute_task):
        task = execute_task('test_dupes_across_tasks_1')
        assert len(task.accepted) == 1, 'didn\'t accept first premiere'
        task = execute_task('test_dupes_across_tasks_2')
        assert len(task.accepted) == 0, 'accepted duplicate premiere'

    def test_path_set(self, execute_task):
        task = execute_task('test_path_set')
        assert task.find_entry(title='foo bar s01e01 hdtv', path='.')

    def test_pilot_and_premiere(self, execute_task):
        task = execute_task('test_pilot_and_premiere')
        assert len(task.accepted) == 2, 'should have accepted pilot and premiere'

    def test_no_teasers(self, execute_task):
        task = execute_task('test_no_teasers')
        assert len(task.accepted) == 1, 'should have accepted only premiere'
        assert not task.find_entry('accepted', title='foo bar s01e00 hdtv')

    def test_multi_episode(self, execute_task):
        task = execute_task('test_multi_episode')
        assert len(task.accepted) == 1, 'should have accepted multi-episode premiere'

    def test_rerun(self, execute_task):
        task = execute_task('test_rerun')
        assert not task.find_entry('accepted', title='theshow s01e02'), 'accepted non-premiere'

    def test_no_rerun_with_series(self, execute_task):
        task = execute_task('test_no_rerun_with_series')
        assert task.find_entry('accepted', title='theshow s01e02'), 'should be accepted by series'

    def test_no_rerun(self, execute_task):
        task = execute_task('test_no_rerun')
        assert not task.find_entry('accepted', title='theshow s01e02'), 'accepted non-premiere'

    def test_no_configured_shows(self, execute_task):
        task = execute_task('test_no_configured_1')
        task = execute_task('test_no_configured_2')
        entry = task.find_entry(title='explicit show s01e01')
        assert not entry.accepted
        entry = task.find_entry(title='other show s01e01')
        assert entry.accepted
