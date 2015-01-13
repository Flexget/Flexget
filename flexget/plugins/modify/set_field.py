from __future__ import unicode_literals, division, absolute_import

import logging
from functools import partial

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('set')


class ModifySet(object):

    """Allows adding information to a task entry for use later.

    Example:

    set:
      path: ~/download/path/
    """

    schema = {
        'type': 'object',
        "minProperties": 1
    }

    def on_task_metainfo(self, task, config):
        """Adds the set dict to all accepted entries."""
        for entry in task.all_entries:
            self.modify(entry, config)

    def modify(self, entry, config, errors=True):
        """This can be called from a plugin to add set values to an entry"""
        orig_field_values = {}
        for field in config:
            # If this doesn't appear to be a jinja template, just set it right away.
            if not isinstance(config[field], basestring) or '{' not in config[field]:
                entry[field] = config[field]
            # Store original values before overwriting with a lazy field, so that set directives can reference
            # themselves.
            elif field in entry:
                orig_field_values[field] = entry.pop(field)
        entry.register_lazy_fields(config, partial(self.lazy_set, config, orig_field_values, errors=errors))

    def lazy_set(self, config, orig_field_values, entry, field, errors=True):
        logger = log.error if errors else log.debug
        if field in orig_field_values:
            entry[field] = orig_field_values[field]
        try:
            entry[field] = entry.render(config[field])
        except RenderError as e:
            logger('Could not set %s for %s: %s' % (field, entry['title'], e))
        return entry.get(field, eval_lazy=False)

@event('plugin.register')
def register_plugin():
    plugin.register(ModifySet, 'set', api_ver=2)
