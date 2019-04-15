from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import aggregate_inputs

log = logging.getLogger('crossmatch')


class CrossMatch(object):
    """
    Perform action based on item on current task and other inputs.

    Example::

      crossmatch:
        from:
          - rss: http://example.com/
        fields:
          - title
        action: reject
        exact: yes
        case_sensitive: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'fields': {'type': 'array', 'items': {'type': 'string'}},
            'action': {'enum': ['accept', 'reject']},
            'from': {'type': 'array', 'items': {'$ref': '/schema/plugins?phase=input'}},
            'exact': {'type': 'boolean', 'default': True},
            'all_fields': {'type': 'boolean', 'default': False},
            'case_sensitive': {'type': 'boolean', 'default': True}
        },
        'required': ['fields', 'action', 'from'],
        'additionalProperties': False,
    }

    def on_task_filter(self, task, config):

        fields = config['fields']
        action = config['action']
        all_fields = config['all_fields']

        match_entries = aggregate_inputs(task, config['from'])

        # perform action on intersecting entries
        for entry in task.entries:
            for generated_entry in match_entries:
                log.trace('checking if %s matches %s', entry['title'], generated_entry['title'])
                common = self.entry_intersects(entry, generated_entry, fields, config.get('exact'), config.get('case_sensitive'))
                if common and (not all_fields or len(common) == len(fields)):
                    msg = 'intersects with %s on field(s) %s' % (
                        generated_entry['title'],
                        ', '.join(common),
                    )
                    for key in generated_entry:
                        if key not in entry:
                            entry[key] = generated_entry[key]
                    if action == 'reject':
                        entry.reject(msg)
                    if action == 'accept':
                        entry.accept(msg)

    def entry_intersects(self, e1, e2, fields=None, exact=True, case_sensitive=True):
        """
        :param e1: First :class:`flexget.entry.Entry`
        :param e2: Second :class:`flexget.entry.Entry`
        :param fields: List of fields which are checked
        :return: List of field names in common
        """

        if fields is None:
            fields = []

        common_fields = []

        for field in fields:
            # Doesn't really make sense to match if field is not in both entries
            if field not in e1 or field not in e2:
                log.trace('field %s is not in both entries', field)
                continue

            if not case_sensitive and isinstance(e1[field], str):
                v1 = e1[field].lower()
            else:
                v1 = e1[field]
            if not case_sensitive and isinstance(e1[field], str):
                v2 = e2[field].lower()
            else:
                v2 = e2[field]

            try:
                if v1 == v2 or not exact and (v2 in v1 or v1 in v2):
                    common_fields.append(field)
                else:
                    log.trace('not matching')
            except TypeError as e:
                # argument of type <type> is not iterable
                log.trace('error matching fields: %s', str(e))

        return common_fields


@event('plugin.register')
def register_plugin():
    plugin.register(CrossMatch, 'crossmatch', api_ver=2)
