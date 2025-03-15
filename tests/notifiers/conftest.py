import pytest

from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name


class DebugNotification:
    schema = {'type': 'object'}

    def __init__(self):
        self.notifications = []

    def notify(self, title, message, config):
        self.notifications.append((title, message, config))


@event('plugin.register')
def register_plugin():
    plugin.register(
        DebugNotification, 'debug_notification', interfaces=['notifiers'], api_ver=2, debug=True
    )


@pytest.fixture
def debug_notifications(manager):
    notifications = get_plugin_by_name('debug_notification').instance.notifications = []
    return notifications
