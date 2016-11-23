from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

__name__ = 'notify_osd'

log = logging.getLogger(__name__)


class OutputNotifyOsd(object):
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'timeout': {'type': 'integer', 'default': 4},
            'template': {'type': 'string', 'format': 'template'}
        },
        'additionalProperties': False
    }

    def notify(self, data):
        try:
            from gi.repository import Notify
        except ImportError as e:
            log.debug('Error importing Notify: %s', e)
            raise plugin.DependencyError(__name__, 'gi.repository', 'Notify module required. ImportError: %s' % e)

        title = data['title']
        body = data['message']

        if not Notify.init("Flexget"):
            log.error('Unable to init libnotify.')
            return

        n = Notify.Notification.new(title, body, None)
        timeout = (data['timeout'] * 1000)
        n.set_timeout(timeout)

        if not n.show():
            log.error('Unable to send notification for %s', title)
            return

        log.verbose('NotifyOSD notification sent.')

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
