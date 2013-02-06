from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.plugin import register_plugin, priority, DependencyError
from flexget.utils.template import RenderError, render_from_task

log = logging.getLogger('notify_osd')


class OutputNotifyOsd(object):

    def validator(self):
        from flexget import validator
        config = validator.factory()
        config.accept('boolean')
        advanced = config.accept('dict')
        advanced.accept('text', key='title_template')
        advanced.accept('text', key='item_template')
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        config.setdefault('title_template', '{{task.name}}')
        config.setdefault('item_template', '{{title}}')
        return config

    def on_task_start(self, task, config):
        try:
            from gi.repository import Notify
        except ImportError as e:
            log.debug('Error importing Notify: %s' % e)
            raise DependencyError('notify_osd', 'gi.repository',
                'Notify module required. ImportError: %s' % e)

    @priority(0)
    def on_task_output(self, task, config):
        """
        Configuration::
            notify_osd:
                title_template: Notification title, supports jinja templating, default {{task.name}}
                item_template: Notification body, suports jinja templating, default {{title}}
        """
        from gi.repository import Notify

        if not Notify.init("Flexget"):
            log.error('Unable to init libnotify.')
            return

        if not task.accepted:
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

        n = Notify.Notification.new(title, '\n'.join(body_items), None)
        n.show()
        n.show()

register_plugin(OutputNotifyOsd, 'notify_osd', api_ver=2)
