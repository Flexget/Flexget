from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import mock


class TestNotifyEntry(object):
    config = """
        tasks:
          test_basic_notify:
            mock:
             - {title: 'foo', url: 'http://bla.com'}
             - {title: 'bar', url: 'http://bla2.com'}
            accept_all: yes
            notify_entry:
              title: "{{title}}"
              message: "{{url}}"
              via:
                - debug_notification:
                    api_key: apikey
        """

    def test_basic_notify(self, debug_notifications, execute_task):
        expected = [('foo', 'http://bla.com', {'api_key': 'apikey'}),
                    ('bar', 'http://bla2.com', {'api_key': 'apikey'})]
        task = execute_task('test_basic_notify')

        assert len(task.accepted) == 2
        assert debug_notifications == expected
