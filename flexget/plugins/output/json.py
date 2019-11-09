from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import logging

from flexget import plugin
from flexget.utils import json
from flexget.event import event

PLUGIN_NAME = 'make_json'

log = logging.getLogger(PLUGIN_NAME)


class OutputJson(object):
    schema = {
        'type': 'object',
        'properties': {'file': {'type': 'string'}},
        'required': ['file'],
        'additionalProperties': False,
    }

    def on_task_output(self, task, config):

        output = os.path.expanduser(config['file'])
        # Output to config directory if absolute path has not been specified
        if not os.path.isabs(output):
            output = os.path.join(task.manager.config_base, output)
        entries = {}
        for entry in task.accepted:
            entry_dict = entry.serialize()
            entries[entry['title']] = entry_dict

        with open(output, 'w') as output_file:
            json.dump(entries, output_file, encode_datetime=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputJson, PLUGIN_NAME, api_ver=2)
