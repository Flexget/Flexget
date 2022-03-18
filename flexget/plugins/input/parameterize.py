from __future__ import absolute_import, division, unicode_literals

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry

log = logging.getLogger('parameterize')


class Parameterize(object):

    schema = {
        'type': 'object',
        'properties': {
            'plugin': {'$ref': '/schema/plugins?phase=input'},
            'using': {'$ref': '/schema/plugins?phase=input'},
        },
    }

    def on_task_input(self, task, config):
        for param_input_name, param_input_config in config['using'].items():
            param_input = plugin.get_plugin_by_name(param_input_name)
            method = param_input.phase_handlers['input']
            try:
                param_entries = method(task, param_input_config)
            except plugin.PluginError as e:
                log.warning('Error during input plugin %s: %s' % (param_input_name, e))
                continue
            for param_entry in param_entries:
                for subj_input_name, subj_input_config in config['plugin'].items():
                    subj_input = plugin.get_plugin_by_name(subj_input_name)
                    method = subj_input.phase_handlers['input']
                    subj_input_config = _parameterize(subj_input_config, param_entry)
                    try:
                        result = method(task, subj_input_config)
                    except plugin.PluginError as e:
                        log.warning('Error during input plugin %s: %s' % (subj_input_name, e))
                        continue
                    for entry in result:
                        yield entry


def _parameterize(element, entry):
    if isinstance(element, dict):
        return dict((k, _parameterize(v, entry)) for k, v in element.items())
    if isinstance(element, list):
        return [_parameterize(v, entry) for v in element]
    if isinstance(element, str) and ('{{' in element or '{%' in element):
        try:
            return render_from_entry(element, entry, native=True)
        except (RenderError, TypeError) as e:
            raise plugin.PluginError('Error parameterizing `%s`: %s' % (element, e), logger=log)
    return element


@event('plugin.register')
def register_plugin():
    plugin.register(Parameterize, 'parameterize', api_ver=2)
