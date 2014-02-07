from __future__ import unicode_literals, division, absolute_import
import logging
import os

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugins.plugin_include import load_plugin_config

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
            'from': {'type': 'array', 'items': {'$ref': '/schema/plugins?phase=input'}},
            'include': {'type': 'array', 'items': one_or_more({'type': 'string'})}
        },
        'required': ['fields', 'action'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):

        fields = config['fields']
        action = config['action']
        inputs = config['from']

        match_entries = []

        for name in config['include']:
            name = os.path.expanduser(name)
            if not os.path.isabs(name):
                name = os.path.join(task.manager.config_base, name)
            include = load_plugin_config(name, 'task')
            # merge
            try:
                inputs.extend([include])
            except MergeException:
                raise plugin.PluginError('Failed to merge include file to task %s, incompatible datatypes' % task.name)

        # TODO: xxx
        # we probably want to have common "run and combine inputs" function sometime soon .. this code is in
        # few places already (discover, inputs, ...)
        # code written so that this can be done easily ...
        for item in inputs:
            for input_name, input_config in item.iteritems():
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
