from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
from functools import partial

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('set')

UNSET = object()


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
        for field in config:
            # If this doesn't appear to be a jinja template, just set it right away.
            if not isinstance(config[field], basestring) or '{' not in config[field]:
                entry[field] = config[field]
            # Store original values before overwriting with a lazy field, so that set directives can reference
            # themselves.
            else:
                orig_value = entry.get(field, UNSET, eval_lazy=False)
                try:
                    del entry[field]
                except KeyError:
                    pass
                entry.register_lazy_func(
                    partial(self.lazy_set, config, field, orig_value, errors=errors), config)

    def lazy_set(self, config, field, orig_field_value, entry, errors=True):
        logger = log.error if errors else log.debug
        if orig_field_value is not UNSET:
            entry[field] = orig_field_value
        try:
            entry[field] = entry.render(config[field])
        except RenderError as e:
            logger('Could not set %s for %s: %s' % (field, entry['title'], e))


@event('plugin.register')
def register_plugin():
    plugin.register(ModifySet, 'set', api_ver=2)
