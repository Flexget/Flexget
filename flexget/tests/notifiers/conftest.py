from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.plugin import get_plugin_by_name


class DebugNotification(object):
    schema = {'type': 'object'}

    def __init__(self):
        self.notifications = []

    def notify(self, title, message, config):
        self.notifications.append((title, message, config))


def pytest_collection_modifyitems(items):
    """
    Add our debug_notification plugin to all tests in this directory.
    """
    for item in items:
        item.add_marker(pytest.mark.register_plugin(DebugNotification, 'debug_notification', interfaces=['notifiers'], api_ver=2, debug=True))


@pytest.fixture()
def debug_notifications(manager):
    notifications = get_plugin_by_name('debug_notification').instance.notifications = []
    return notifications
