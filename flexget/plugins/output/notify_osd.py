from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('notify_osd')


class NotifyOsd(object):
    def __init__(self, task, scope, iterate_on, test, plugin_config):
        """
        Notify OSD.

        :param task: The task instance
        :param scope: Notification scope, can be either "entries" or "task"
        :param iterate_on: The entry container to iterate on (such as task.accepted). If scope is "task" it is unneeded.
        :param test: Test mode, task.options.test
        :param plugin_config: The notifier plugin config
        """
        self.task = task
        self.scope = scope
        if scope == 'entries':
            self.iterate_on = iterate_on
        elif scope == 'task':
            self.iterate_on = [[task]]
        else:
            raise ValueError('scope must be \'entries\' or \'task\'')
        self.test_mode = test
        self.config = self.prepare_config(plugin_config)

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        config.setdefault('title_template', '{{task.name}}')
        config.setdefault('item_template', '{{title}}')
        config.setdefault('timeout', 4)
        return config

    def notify(self):
        if not self.iterate_on:
            log.debug('did not have any entities to iterate on')
            return

        from gi.repository import Notify

        for container in self.iterate_on:
            for entity in container:
                body_items = []
                try:
                    body_items.append(entity.render(self.config['item_template']))
                except RenderError as e:
                    log.error('Error setting body message: %s', e)
                log.verbose("Send Notify-OSD notification about: %s", " - ".join(body_items))

                title = self.config['title_template']
                try:
                    title = entity.render(title)
                    log.debug('Setting bubble title to :%s', title)
                except RenderError as e:
                    log.error('Error setting title Notify-osd message: %s', e)

                if not Notify.init("Flexget"):
                    log.error('Unable to init libnotify.')
                    return

                n = Notify.Notification.new(title, '\n'.join(body_items), None)
                timeout = (self.config['timeout'] * 1000)
                n.set_timeout(timeout)

                if not n.show():
                    log.error('Unable to send notification for %s', title)
                    return


class OSDNotifier(object):
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

    def on_task_start(self, task, config):
        try:
            from gi.repository import Notify  # noqa
        except ImportError as e:
            log.debug('Error importing Notify: %s', e)
            raise plugin.DependencyError('notify_osd', 'gi.repository', 'Notify module required. ImportError: %s' % e)

    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        return NotifyOsd(task, 'entries', [task.accepted], task.options.test, config).notify()

    def notify(self, task, scope, iterate_on, test, config):
        return NotifyOsd(task, scope, iterate_on, test, config).notify()


@event('plugin.register')
def register_plugin():
    plugin.register(OSDNotifier, 'notify_osd', api_ver=2, groups=['notifiers'])
