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
        field:
          - imdb_id
          - movie_name
        action: reject
        first: true # Allow first instance
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'array'},
                ]
            },
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

    def extract_fields(self, entry, field_names):
        ret = []
        for field in field_names:
            if field in entry:
                ret.append(entry[field])
            else:
                ret.append(None)
        return ret

    def on_task_filter(self, task, config):
        config = self.prepare_config(config)
        field_names = config['field']
        # Convert to list
        if not isinstance(field_names, list):
            field_names = [field_names]
        action = config['action']
        entries = list(task.entries)
        entry_len = len(entries)
        for i in range(entry_len):
            entry = entries[i]
            entry_fields = self.extract_fields(entry,field_names)
            # Ignore rejected entires
            if entry.rejected:
                continue
            for j in range(i+1, entry_len):
                prospect = entries[j]
                prospect_fields = self.extract_fields(prospect,field_names)
                # Ignore rejected entires
                if prospect.rejected: continue
                if entry_fields == prospect_fields and any(entry_fields):
                    msg = 'Field {} value {} equals on {} and {}'.format(
                        field_names, entry_fields, entry['title'], prospect['title'])
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
