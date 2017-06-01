from __future__ import unicode_literals, division, absolute_import

import pytest

from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.utils.tools import merge_by_prefix

plugin_name = 'debug_notification'


class DebugNotification(object):
    schema = {'type': 'object'}

    def __init__(self):
        self.notifications = []

    def notify(self, title, message, config, entry=None):
        if entry:
            merge_by_prefix(plugin_name + '_', dict(entry), config)
        self.notifications.append((title, message, config))


@event('plugin.register')
def register_plugin():
    plugin.register(DebugNotification, plugin_name, interfaces=['notifiers'], api_ver=2, debug=True)


@pytest.fixture()
def debug_notifications(manager):
    notifications = get_plugin_by_name(plugin_name).instance.notifications = []
    return notifications
