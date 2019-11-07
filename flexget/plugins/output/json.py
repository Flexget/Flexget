from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import json
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_task, get_template, RenderError

PLUGIN_NAME = 'make_json'

log = logging.getLogger(PLUGIN_NAME)


class OutputJson(object):
    schema = {
        'type': 'object',
        'properties': {'template': {'type': 'string'}, 'file': {'type': 'string'}},
        'required': ['file'],
        'additionalProperties': False,
    }

    def on_task_output(self, task, config):
        # Use the default template if none is specified
        if not config.get('template'):
            config['template'] = 'json.template'

        filename = os.path.expanduser(config['template'])
        output = os.path.expanduser(config['file'])
        # Output to config directory if absolute path has not been specified
        if not os.path.isabs(output):
            output = os.path.join(task.manager.config_base, output)

        json.dump(output)

@event('plugin.register')
def register_plugin():
    plugin.register(OutputJson, PLUGIN_NAME, api_ver=2)
