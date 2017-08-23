from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('wordpress_auth')


class PluginWordpress(object):

    schema = {'type': 'object',
              'properties': {
                  'url': {'type': 'string', 'oneOf': [{'format': 'url'}]},
                  'username': {'type': 'string'},
                  'password': {'type': 'string'}
              },
              'required': ['url'],
              'additionalProperties': False}

    @plugin.priority(135)
    def on_task_start(self, task, config):
        pass


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordpress, 'wordpress_auth', api_ver=2)