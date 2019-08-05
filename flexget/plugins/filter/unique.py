from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('unique')


class Unique(object):
    """
    Take action on entries with duplicate fields, except for the first item

    Reject the second+ instance of every movie:

      unique:
        field:
          - imdb_id
          - movie_name
        action: reject
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': one_or_more({'type': 'string'}),
            'action': {'enum': ['accept', 'reject']},
        },
        'required': ['field'],
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        if isinstance(config, bool) or config is None:
            config = {}
        config.setdefault('action', 'reject')
        if not isinstance(config['field'], list):
            config['field'] = [config['field']]
        return config

    def extract_fields(self, entry, field_names):
        return [entry[field] for field in field_names]

    def should_ignore(self, item, action):
        return item.accepted and action == 'accept' or item.rejected and action == 'reject'

    def on_task_filter(self, task, config):
        config = self.prepare_config(config)
        field_names = config['field']
        entries = list(task.entries)
        for i, entry in enumerate(entries):
            # Ignore already processed entries
            if self.should_ignore(entry, config['action']):
                continue
            try:
                entry_fields = self.extract_fields(entry, field_names)
            # Ignore if a field is missing
            except KeyError:
                continue
            # Iterate over next items, try to find a similar item
            for prospect in entries[i + 1 :]:
                # Ignore processed prospects
                if self.should_ignore(prospect, config['action']):
                    continue
                try:
                    prospect_fields = self.extract_fields(prospect, field_names)
                # Ignore if a field is missing
                except KeyError:
                    continue
                if entry_fields and entry_fields == prospect_fields:
                    msg = 'Field {} value {} equals on {} and {}'.format(
                        field_names, entry_fields, entry['title'], prospect['title']
                    )
                    # Mark prospect
                    if config['action'] == 'accept':
                        prospect.accept(msg)
                    else:
                        prospect.reject(msg)


@event('plugin.register')
def register_plugin():
    plugin.register(Unique, 'unique', api_ver=2)
