from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('duplicates')


class Duplicates(object):
    """
    Take action on entries with duplicate field values

    Example::

      duplicates:
        field: <field name>
        action: [accept|reject]
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {'type': 'string'},
            'action': {'enum': ['accept', 'reject']},
        },
        'required': ['field', 'action'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):
        field = config['field']
        action = config['action']
        for entry in task.entries:
            for prospect in task.entries:
                if entry == prospect:
                    continue
                if entry.get(field) is not None and entry[field] == prospect.get(field):
                    msg = 'Field {} value {} equals on {} and {}'.format(
                        field, entry[field], entry['title'], prospect['title'])
                    if action == 'accept':
                        entry.accept(msg)
                    else:
                        entry.reject(msg)


@event('plugin.register')
def register_plugin():
    plugin.register(Duplicates, 'duplicates', api_ver=2)
