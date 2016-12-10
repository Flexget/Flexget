from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import copy

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.template import RenderError, get_template

log = logging.getLogger('notify')

ENTRY_CONTAINERS = ['entries', 'accepted', 'rejected', 'failed', 'undecided']
DEFAULT_DICTS = {
    'task': {
        'message': 'Task returned {{ task.accepted|length }} accepted entries',
        'title': '{{ task_name }}',
        'url': ''
    },

    'entries': {
        'message': '{% if series_name is defined %}'
                   '{{ tvdb_series_name|d(series_name) }} '
                   '{{series_id}} {{tvdb_ep_name|d('')}}'
                   '{% elif imdb_name is defined %}'
                   '{{imdb_name}} {{imdb_year}}'
                   '{% elif title is defined %}'
                   '{{ title }}'
                   '{% endif %}',
        'url': '{% if imdb_url is defined %}'
               '{{imdb_url}}'
               '{% endif %}',
        'title': '{{ task_name }}'
    }
}


class NotifyBase(object):
    schema = {
        'type': 'object',
        'properties': {
            'to': {
                'type': 'array', 'items':
                    {'allOf': [
                        {'$ref': '/schema/plugins?group=notifiers'},
                        {'maxProperties': 1,
                         'error_maxProperties': 'Plugin options indented 2 more spaces than the first letter of the'
                                                ' plugin name.',
                         'minProperties': 1}]}},
            'what': one_or_more({'type': 'string', 'enum': ENTRY_CONTAINERS}),
            'scope': {'type': 'string', 'enum': ['task', 'entries']},
        },
        'required': ['to'],
        'additionalProperties': True
    }


class Notify(object):
    def send_notification(self, title, body, notifiers, template_renderer=None):
        if template_renderer:
            try:
                title = template_renderer(title)
            except RenderError as e:
                log.error('Error rendering notification title: %s', e)
            try:
                body = template_renderer(body)
            except RenderError as e:
                log.error('Error rendering notification body: %s', e)
        for notifier in notifiers:
            for notifier_name, notifier_config in notifier.items():
                notifier = plugin.get_plugin_by_name(notifier_name).instance

                rendered_config = {}

                # If a template renderer is specified, try to render all the notifier config values
                if template_renderer:
                    for attribute, value in notifier_config.items():
                        try:
                            rendered_config[attribute] = template_renderer(value)
                        except RenderError as e:
                            log.error('Error rendering %s config field %s: %s', notifier_name, attribute, e)
                            rendered_config[attribute] = notifier_config[attribute]
                else:
                    rendered_config = notifier_config

                log.debug('Sending a notification to `%s`', notifier_name)
                try:
                    notifier.notify(title, body, rendered_config)  # TODO: Update notifiers for new api
                except PluginWarning as e:
                    log.warning('Error while sending notification to `%s`: %s', notifier_name, e.value)
                else:
                    log.verbose('Successfully sent a notification to `%s`', notifier_name)


class NotifyEntries(NotifyBase):
    def on_task_exit(self, task, config):
        config['scope'] = 'entries'
        plugin.get_plugin_by_name('notify').instance.send_notification(task, config)


class NotifyAbort(NotifyBase):
    def on_task_abort(self, task, config):
        if task.silent_abort:
            return

        title = 'Task {{ task_name }} has aborted!'
        message = 'Reason: {{ task.abort_reason }}'
        notify_config = {'to': config['to'],
                         'scope': 'task',
                         'title': title,
                         'message': message}
        log.debug('sending abort notification')
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)
    plugin.register(NotifyEntries, 'notify_entries', api_ver=2)
    plugin.register(NotifyAbort, 'notify_abort', api_ver=2)

    plugin.register_task_phase('notify', before='exit')  # TODO: something so this phase doesn't cause aborts
