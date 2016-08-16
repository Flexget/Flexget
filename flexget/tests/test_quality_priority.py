from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest
from jinja2 import Template

from flexget.plugins.parsers.parser_guessit import ParserGuessit
from flexget.plugins.parsers.parser_internal import ParserInternal
from flexget.utils.qualities import Quality


class TestQualityPriority(object):
    config = """
        tasks:
          test_quality_priority:
            mock:
              - {title: 'Some Show S01E01 WEBRip'}
              - {title: 'Some Show S01E01 HDTV'}
            quality_priority:
              webrip: 155
            series:
              - Some Show:
                  identified_by: ep
          test_normal_quality_priority:
            mock:
              - {title: 'Some Show S01E02 WEBRip'}
              - {title: 'Some Show S01E02 HDTV'}
            series:
              - Some Show:
                  identified_by: ep
    """

    def test_quality_priority(self, execute_task):
        task = execute_task('test_quality_priority')

        assert task.find_entry('accepted', title='Some Show S01E01 WEBRip'), 'WEBRip should have been accepted'

        task = execute_task('test_normal_quality_priority')
        assert task.find_entry('accepted', title='Some Show S01E02 HDTV'), 'HDTV should have been accepted'
