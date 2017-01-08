from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin


class TestInterfaces(object):
    """Test that any plugins declaring certain interfaces at least superficially comply with those interfaces."""
    def test_task_interface(self):
        plugin.load_plugins()
        task_plugins = plugin.get_plugins(interface='task')
        for p in task_plugins:
            assert isinstance(p.schema, dict), 'Task interface requires a schema to be defined.'
            assert p.phase_handlers, 'Task plugins should have at least on phase handler (on_task_X) method.'


    def test_list_interface(self):
        plugin.load_plugins()
        task_plugins = plugin.get_plugins(interface='list')
        for p in task_plugins:
            assert isinstance(p.schema, dict), 'List interface requires a schema to be defined.'
            assert hasattr(p.instance, 'get_list'), 'List plugins must implement a get_list method.'
