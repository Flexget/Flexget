from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_task, get_template, RenderError

PLUGIN_NAME = 'make_html'

log = logging.getLogger(PLUGIN_NAME)


class OutputHtml(object):
    schema = {
        'type': 'object',
        'properties': {'template': {'type': 'string'}, 'file': {'type': 'string'}},
        'required': ['file'],
        'additionalProperties': False,
    }

    def on_task_output(self, task, config):
        # Use the default template if none is specified
        if not config.get('template'):
            config['template'] = 'html.template'

        filename = os.path.expanduser(config['template'])
        output = os.path.expanduser(config['file'])
        # Output to config directory if absolute path has not been specified
        if not os.path.isabs(output):
            output = os.path.join(task.manager.config_base, output)

        # create the template
        try:
            template = render_from_task(get_template(filename), task)
            log.verbose('Writing output html to %s', output)
            with open(output, 'wb') as f:
                f.write(template.encode('utf-8'))
        except RenderError as e:
            log.error('Error while rendering task %s, Error: %s', task, e)
            raise plugin.PluginError('There was an error rendering the specified template')


@event('plugin.register')
def register_plugin():
    plugin.register(OutputHtml, PLUGIN_NAME, api_ver=2)
