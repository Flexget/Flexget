import pytest
from jinja2 import Template

import flexget.utils.qualities as qualities
from flexget.task import TaskAbort


class TestAssumeQuality:
    _config = """
        templates:
          global:
            parsing:
              series: {{parser}}
              movie: {{parser}}
            mock:
              - {title: 'Testfile[h264-720p]'}
              - {title: 'Testfile.1280x720'}
              - {title: 'Testfile.HDTV'}
              - {title: 'Testfile.cam'}
              - {title: 'Testfile.noquality'}
              - {title: 'Testfile.xvid.mp3'}
            accept_all: yes
        tasks:
          test_default:
            assume_quality:
              720p: flac
              h264: 10bit
              HDTV: truehd
              any: 720p h264

          test_simple:
            assume_quality: 720p h264

          test_priority:
            assume_quality:
              720p: mp3
              720p h264: flac
              h264: mp3

          test_matching:
            assume_quality:
              hdtv: 720p

          test_negative_matching:
            assume_quality:
              '!xvid !divx !mp3': 1080p

          test_no_clobber:
            assume_quality:
              720p: xvid

          test_invalid_target:
            assume_quality:
              potato: 720p

          test_with_series:
            template: no_global
            mock:
            - title: my show S01E01 hdtv
            assume_quality: 720p
            series:
            - my show:
                quality: 720p hdtv

          test_with_series_target:
            template: no_global
            mock:
            - title: my show S01E01 hdtv
            assume_quality: 720p
            series:
            - my show:
                target: 720p hdtv

          test_with_series_qualities:
            template: no_global
            mock:
            - title: my show S01E01 hdtv
            assume_quality: 720p
            series:
            - my show:
                qualities: [720p hdtv]
    """

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture."""
        return Template(self._config).render({'parser': request.param})

    def test_matching(self, execute_task):
        task = execute_task('test_matching')
        entry = task.find_entry('entries', title='Testfile.HDTV')
        assert entry.get('quality') == qualities.Quality('720p HDTV')

    def test_negative_matching(self, execute_task):
        task = execute_task('test_negative_matching')
        entry = task.find_entry('entries', title='Testfile.HDTV')
        assert entry.get('quality') == qualities.Quality('1080p HDTV')

        entry = task.find_entry('entries', title='Testfile.xvid.mp3')
        assert entry.get('quality') == qualities.Quality('xvid mp3')

    def test_no_clobber(self, execute_task):
        task = execute_task('test_no_clobber')
        entry = task.find_entry('entries', title='Testfile[h264-720p]')
        assert entry.get('quality') != qualities.Quality('720p xvid')
        assert entry.get('quality') == qualities.Quality('720p h264')

    def test_default(self, execute_task):
        task = execute_task('test_default')
        entry = task.find_entry('entries', title='Testfile.noquality')
        assert entry.get('quality') == qualities.Quality('720p h264'), (
            'Testfile.noquality quality not \'720p h264\''
        )

    def test_simple(self, execute_task):
        task = execute_task('test_simple')
        entry = task.find_entry('entries', title='Testfile.noquality')
        assert entry.get('quality') == qualities.Quality('720p h264'), (
            'Testfile.noquality quality not \'720p h264\''
        )

    def test_priority(self, execute_task):
        task = execute_task('test_priority')
        entry = task.find_entry('entries', title='Testfile[h264-720p]')
        assert entry.get('quality') != qualities.Quality('720p h264 mp3')
        assert entry.get('quality') == qualities.Quality('720p h264 flac')

    def test_invalid_target(self, execute_task):
        with pytest.raises(TaskAbort):
            execute_task('test_invalid_target')

    def test_with_series(self, execute_task):
        task = execute_task('test_with_series')
        assert task.accepted, 'series plugin should have used assumed quality'

    def test_with_series_target(self, execute_task):
        task = execute_task('test_with_series_target')
        assert task.accepted, 'series plugin should have used assumed quality'

    def test_with_series_qualities(self, execute_task):
        task = execute_task('test_with_series_qualities')
        assert task.accepted, 'series plugin should have used assumed quality'
