from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import get_template


log = logging.getLogger('notify_task')


class NotifyTask(object):
    schema = {
        'type': 'object',
        'properties': {
            'title': {
                'type': 'string',
                'default': '[FlexGet] {{task.name}}:'
                           '{%if task.failed %} {{task.failed|length}} failed entries.{% endif %}'
                           '{% if task.accepted %} {{task.accepted|length}} new entries downloaded.{% endif %}'},
            'template': {'type': 'string', 'default': 'default.template'},
            'via': {
                'type': 'array', 'items':
                    {'allOf': [
                        {'$ref': '/schema/plugins?group=notifiers'},
                        {'maxProperties': 1,
                         'error_maxProperties': 'Plugin options indented 2 more spaces than the first letter of the'
                                                ' plugin name.',
                         'minProperties': 1}]}}

        },
        'required': ['via']
    }

    def on_task_notify(self, task, config):
        send_notification = plugin.get_plugin_by_name('notify').instance.send_notification
        if not (task.accepted or task.failed):
            log.verbose('No accepted or failed entries, not sending a notification.')
            return
        send_notification(config['title'],
                          get_template(config['template'], 'task'),
                          config['via'],
                          template_renderer=task.render)


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyTask, 'notify_task', api_ver=2)
