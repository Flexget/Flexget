from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError, render_from_task

log = logging.getLogger('notify_osd')


class OutputNotifyOsd(object):
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'title_template': {'type': 'string'},
                    'item_template': {'type': 'string'},
                    'timeout': {'type': 'integer'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        config.setdefault('title_template', '{{task.name}}')
        config.setdefault('item_template', '{{title}}')
        config.setdefault('timeout', 4)
        return config

    def on_task_start(self, task, config):
        try:
            from gi.repository import Notify
        except ImportError as e:
            log.debug('Error importing Notify: %s' % e)
            raise plugin.DependencyError('notify_osd', 'gi.repository', 'Notify module required. ImportError: %s' % e)

    @plugin.priority(0)
    def on_task_output(self, task, config):
        """
        Configuration::
            notify_osd:
                title_template: Notification title, supports jinja templating, default {{task.name}}
                item_template: Notification body, suports jinja templating, default {{title}}
                timeout: Set how long the Notification is displayed, this is an integer default = 4 seconds, Default: 4
        """
        from gi.repository import Notify

        if not config or not task.accepted:
            return

        config = self.prepare_config(config)
        body_items = []
        for entry in task.accepted:
            try:
                body_items.append(entry.render(config['item_template']))
            except RenderError as e:
                log.error('Error setting body message: %s' % e)
        log.verbose("Send Notify-OSD notification about: %s", " - ".join(body_items))

        title = config['title_template']
        try:
            title = render_from_task(title, task)
            log.debug('Setting bubble title to :%s', title)
        except RenderError as e:
            log.error('Error setting title Notify-osd message: %s' % e)

        if not Notify.init("Flexget"):
            log.error('Unable to init libnotify.')
            return

        n = Notify.Notification.new(title, '\n'.join(body_items), None)
        timeout = (config['timeout'] * 1000)
        n.set_timeout(timeout)

        if not n.show():
            log.error('Unable to send notification for %s', title)
            return


@event('plugin.register')
def register_plugin():
    plugin.register(OutputNotifyOsd, 'notify_osd', api_ver=2)
