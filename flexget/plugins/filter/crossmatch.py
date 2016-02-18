from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

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
    """

    schema = {
        'type': 'object',
        'properties': {
            'fields': {'type': 'array', 'items': {'type': 'string'}},
            'action': {'enum': ['accept', 'reject']},
            'from': {'type': 'array', 'items': {'$ref': '/schema/plugins?phase=input'}}
        },
        'required': ['fields', 'action', 'from'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):

        fields = config['fields']
        action = config['action']

        match_entries = []

        # TODO: xxx
        # we probably want to have common "run and combine inputs" function sometime soon .. this code is in
        # few places already (discover, inputs, ...)
        # code written so that this can be done easily ...
        for item in config['from']:
            for input_name, input_config in item.items():
                input = plugin.get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise plugin.PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except plugin.PluginError as e:
                    log.warning('Error during input plugin %s: %s' % (input_name, e))
                    continue
                if result:
                    match_entries.extend(result)
                else:
                    log.warning('Input %s did not return anything' % input_name)
                    continue

        # perform action on intersecting entries
        for entry in task.entries:
            for generated_entry in match_entries:
                log.trace('checking if %s matches %s' % (entry['title'], generated_entry['title']))
                common = self.entry_intersects(entry, generated_entry, fields)
                if common:
                    msg = 'intersects with %s on field(s) %s' % \
                          (generated_entry['title'], ', '.join(common))
                    entry.update(generated_entry)
                    if action == 'reject':
                        entry.reject(msg)
                    if action == 'accept':
                        entry.accept(msg)

    def entry_intersects(self, e1, e2, fields=None):
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
            # TODO: simplify if seems to work (useless debug)
            log.trace('checking field %s' % field)
            v1 = e1.get(field, object())
            v2 = e2.get(field, object())
            log.trace('v1: %r' % v1)
            log.trace('v2: %r' % v2)

            if v1 == v2:
                common_fields.append(field)
            else:
                log.trace('not matching')
        return common_fields


@event('plugin.register')
def register_plugin():
    plugin.register(CrossMatch, 'crossmatch', api_ver=2)
