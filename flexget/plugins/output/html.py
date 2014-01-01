from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_task, get_template

PLUGIN_NAME = 'make_html'

log = logging.getLogger(PLUGIN_NAME)


class OutputHtml:

    schema = {
        'type': 'object',
        'properties': {
            'template': {'type': 'string'},
            'file': {'type': 'string'}
        },
        'required': ['file'],
        'additionalProperties': False
    }

    def on_task_output(self, task, config):
        # Use the default template if none is specified
        if not config.get('template'):
            config['template'] = 'default.template'

        filename = os.path.expanduser(config['template'])
        output = os.path.expanduser(config['file'])
        # Output to config directory if absolute path has not been specified
        if not os.path.isabs(output):
            output = os.path.join(task.manager.config_base, output)

        # create the template
        template = render_from_task(get_template(filename, PLUGIN_NAME), task)

        log.verbose('Writing output html to %s' % output)
        with open(output, 'w') as f:
            f.write(template.encode('utf-8'))

@event('plugin.register')
def register_plugin():
    plugin.register(OutputHtml, PLUGIN_NAME, api_ver=2)
