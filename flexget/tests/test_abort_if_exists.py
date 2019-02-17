from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.task import TaskAbort


class TestAbortIfExists(object):
    config = """
        templates:
          global:
            disable: [seen]
            mock:
              - {title: 'test', location: 'mock://some_file.lftp-get-status'}
              - {title: 'test2', location: 'mock://some_file.mkv'}
        tasks:
          test_abort:
            abort_if_exists:
              regexp: '.*\.lftp-get-status'
              field: 'location'
          test_not_abort:
            abort_if_exists:
              regexp: '.*\.lftp-get-status'
              field: 'title'
    """

    def test_abort(self, execute_task):
        with pytest.raises(TaskAbort):
            task = execute_task('test_abort')

    def test_not_abort(self, execute_task):
        task = execute_task('test_not_abort')
        assert not task.aborted, 'Task should have aborted'
