import pytest


@pytest.mark.require_optional_deps
class TestCheckSubtitles:
    config = """
      tasks:
        check_subs:
          mock:
            - {title: 'The Walking Dead S06E08', location:
               'check_subtitles_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'}
            - {title: "The.Big.Bang.Theory.S09E09",
               location: "check_subtitles_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.mkv"}
          check_subtitles: yes
          accept_all: yes
    """

    def test_check_subtitles(self, execute_task):
        task = execute_task('check_subs')
        entry = task.find_entry(title='The Walking Dead S06E08')
        assert entry.get('subtitles') is None
        entry = task.find_entry(title='The.Big.Bang.Theory.S09E09')
        assert set(entry.get('subtitles')) == {'en', 'zh'}
