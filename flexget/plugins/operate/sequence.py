from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('sequence')


class PluginSequence(object):
    """ Allows the same plugin to be configured multiple times in a task.

    Example:
    sequence:
      - rss: http://feeda.com
      - rss: http://feedb.com
    """

    schema = {'type': 'array', 'items': {'$ref': '/schema/plugins'}}

    def __getattr__(self, item):
        """Returns a function for all on_task_* events, that runs all the configured plugins."""
        for phase, method in plugin.phase_methods.items():
            if item == method and phase not in ['accept', 'reject', 'fail']:
                break
        else:
            raise AttributeError(item)

        def handle_phase(task, config):
            """Function that runs all of the configured plugins which act on the current phase."""
            # Keep a list of all results, for input plugin combining
            results = []
            for item in config:
                for plugin_name, plugin_config in item.items():
                    if phase in plugin.get_phases_by_plugin(plugin_name):
                        method = plugin.get_plugin_by_name(plugin_name).phase_handlers[phase]
                        log.debug('Running plugin %s' % plugin_name)
                        result = method(task, plugin_config)
                        if isinstance(result, list):
                            results.extend(result)
            return results

        return handle_phase


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSequence, 'sequence', api_ver=2, debug=True)
