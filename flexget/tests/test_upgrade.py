from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
from jinja2 import Template

from flexget.plugins.parsers.parser_guessit import ParserGuessit
from flexget.plugins.parsers.parser_internal import ParserInternal
from flexget.utils.qualities import Quality


class TestUpgrade(object):
    _config = """
        templates:
          global:
            parsing:
              series: {{parser}}
              movie: {{parser}}
            mock:
              - {title: 'Smoke.1280x720'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
              - {title: 'Smoke.HR'}
            accept_all: yes
        tasks:
          qual:
            quality:
              - hdtv
              - 720p
          min:
            quality: HR+
          max:
            quality: "<=cam <HR"
          min_max:
            quality: HR-720i
    """

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture."""
        return Template(self._config).render({'parser': request.param})

    def test_quality(self, execute_task):
        task = execute_task('qual')
        entry = task.find_entry('rejected', title='Smoke.cam')
        assert entry, 'Smoke.cam should have been rejected'

        entry = task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in task.accepted, '720p should be accepted'
        assert len(task.rejected) == 2, 'wrong number of entries rejected'
        assert len(task.accepted) == 2, 'wrong number of entries accepted'

    def test_min(self, execute_task):
        task = execute_task('min')
        entry = task.find_entry('rejected', title='Smoke.HDTV')
        assert entry, 'Smoke.HDTV should have been rejected'

        entry = task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in task.accepted, '720p should be accepted'
        assert len(task.rejected) == 2, 'wrong number of entries rejected'
        assert len(task.accepted) == 2, 'wrong number of entries accepted'

    def test_max(self, execute_task):
        task = execute_task('max')
        entry = task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = task.find_entry(title='Smoke.cam')
        assert entry, 'entry not found?'
        assert entry in task.accepted, 'cam should be accepted'
        assert len(task.rejected) == 3, 'wrong number of entries rejected'
        assert len(task.accepted) == 1, 'wrong number of entries accepted'

    def test_min_max(self, execute_task):
        task = execute_task('min_max')
        entry = task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = task.find_entry(title='Smoke.HR')
        assert entry, 'entry not found?'
        assert entry in task.accepted, 'HR should be accepted'
        assert len(task.rejected) == 3, 'wrong number of entries rejected'
        assert len(task.accepted) == 1, 'wrong number of entries accepted'


class TestQualityAudio(object):
    config = """
        tasks:
          test_dd_audio_channels:
            quality: "dd+5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD+7.1'}
              - {title: 'My Show S01E05 720p HDTV DD+5.0'}
          test_dd_audio_min:
            quality: ">dd5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+2.0'}
          test_dd_audio_max:
            quality: "<=dd5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+7.1'}
    """

    def test_dd_audio_channels(self, execute_task):
        task = execute_task('test_dd_audio_channels')
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+7.1')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD+7.1" should not have been rejected'
        assert entry['quality'].audio == 'dd+5.1', 'audio "dd+7.1" should have been parsed as dd+5.1'

        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+5.0')
        assert entry['quality'].audio == 'dd+5.1', 'audio "dd+5.0" should have been parsed as dd+5.1'

    def test_dd_audio_min(self, execute_task):
        task = execute_task('test_dd_audio_min')
        assert len(task.rejected) == 1, 'should have rejected one'
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+2.0')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD+2.0" should not have been rejected'
        assert entry['quality'].audio == 'dd+5.1', 'audio should have been parsed as dd+5.1'

    def test_dd_audio_max(self, execute_task):
        task = execute_task('test_dd_audio_max')
        assert len(task.rejected) == 2, 'should have rejected two'
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD5.1')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD5.1" should not have been rejected'
        assert entry['quality'].audio == 'dd5.1', 'audio should have been parsed as dd5.1'
