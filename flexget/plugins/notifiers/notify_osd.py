from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning, DependencyError

__name__ = 'notify_osd'

log = logging.getLogger(__name__)


class OutputNotifyOsd(object):
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'timeout': {'type': 'integer', 'default': 4},
            'file_template': {'type': 'string'}
        },
        'additionalProperties': False
    }

    def notify(self, title, message, timeout, **kwargs):
        """
        Send a notification to NotifyOSD

        :param str title: Notification title
        :param message: Notification message
        :param timeout: Notification timeout
        """
        try:
            from gi.repository import Notify
        except ImportError as e:
            log.debug('Error importing Notify: %s', e)
            raise DependencyError(__name__, 'gi.repository', 'Notify module required. ImportError: %s' % e)

        if not Notify.init("Flexget"):
            raise PluginWarning('Unable to init libnotify.')

        n = Notify.Notification.new(title, message, None)
        timeout = (timeout * 1000)
        n.set_timeout(timeout)

        if not n.show():
            raise PluginWarning('Unable to send notification for %s' % title)

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputNotifyOsd, __name__, api_ver=2, groups=['notifiers'])
