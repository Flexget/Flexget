from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

import itertools
from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.template import get_template


log = logging.getLogger('notify_entry')

ENTRY_CONTAINERS = ['entries', 'accepted', 'rejected', 'failed', 'undecided']


class NotifyEntry(object):
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'default': '{{ title }}'},
            'message': {
                'type': 'string',
                'default': '{% if series_name is defined %}'
                           '{{ tvdb_series_name|d(series_name) }} '
                           '{{series_id}} {{tvdb_ep_name|d('')}}'
                           '{% elif imdb_name is defined %}'
                           '{{imdb_name}} {{imdb_year}}'
                           '{% elif title is defined %}'
                           '{{ title }}'
                           '{% endif %}'
            },
            'template': {'type': 'string'},
            'what': one_or_more({'type': 'string', 'enum': ENTRY_CONTAINERS}),
            'via': {
                'type': 'array', 'items':
                    {'allOf': [
                        {'$ref': '/schema/plugins?group=notifiers'},
                        {'maxProperties': 1,
                         'error_maxProperties': 'Plugin options indented 2 more spaces than the first letter of the'
                                                ' plugin name.',
                         'minProperties': 1}]}}

        },
        'required': ['via'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        config.setdefault('what', ['accepted'])
        if not isinstance(config['what'], list):
            config['what'] = [config['what']]
        return config

    def on_task_notify(self, task, config):
        send_notification = plugin.get_plugin_by_name('notify').instance.send_notification
        config = self.prepare_config(config)
        entries = list(itertools.chain(getattr(task, what) for what in config['what']))
        if not entries:
            log.debug('No entries to notify about.')
            return
        # If a file template is defined, it overrides message
        if config.get('template'):
            body = get_template(config['template'], 'entry')
        else:
            body = config['message']
        for entry in entries:
            send_notification(config['title'], body, config['via'], template_renderer=entry.render)


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyEntry, 'notify_entry', api_ver=2)
