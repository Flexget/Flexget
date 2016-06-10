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

    Reject the second+ instance of every movie:

      duplicates:
        field: imdb_id
        action: reject
        first: true # Allow first instance
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {'type': 'string'},
            'action': {'enum': ['accept', 'reject']},
            'first': {'type': 'boolean'},
        },
        'required': ['field', 'action'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        if config is None:
            config = {}
        config.setdefault('first', True)
        return config

    def on_task_filter(self, task, config):
        config = self.prepare_config(config)
        field = config['field']
        action = config['action']
        entries = list(task.entries)
        entry_len = len(entries)
        for i in range(entry_len):
            entry = entries[i]
            # Ignore rejected entires
            if entry.rejected:
                continue
            for j in range(i+1, entry_len):
                prospect = entries[j]
                # Ignore rejected entires
                if prospect.rejected: continue
                if entry[field] == prospect[field] and entry[field] is not None:
                    msg = 'Field {} value {} equals on {} and {}'.format(
                        field, entry[field], entry['title'], prospect['title'])
                    # Only process first if intended
                    if config['first']:
                        if action == 'accept':
                            entry.accept(msg)
                        else:
                            entry.reject(msg)
                    # Definitely act on second item
                    if action == 'accept':
                        prospect.accept(msg)
                    else:
                        prospect.reject(msg)


@event('plugin.register')
def register_plugin():
    plugin.register(Duplicates, 'duplicates', api_ver=2)
