from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event


log = logging.getLogger('notify_abort')


class NotifyAbort(object):
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'default': 'Task {{ task.name }} has aborted!'},
            'message': {'type': 'string', 'default': 'Reason: {{ task.abort_reason }}'},
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

    def on_task_abort(self, task, config):
        send_notification = plugin.get_plugin_by_name('notify_').instance.send_notification
        if task.silent_abort:
            return
        log.debug('sending abort notification')
        send_notification(config['title'], config['message'], config['via'], template_renderer=task.render)


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyAbort, 'notify_abort', api_ver=2)
