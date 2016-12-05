from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('headers')


class PluginHeaders(object):
    """Allow setting up any headers in all requests (which use urllib2)

    Example:

    headers:
      cookie: uid=<YOUR UID>; pass=<YOUR PASS>
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'string'}}

    @plugin.priority(130)
    def on_task_start(self, task, config):
        """Task starting"""
        # Set the headers for this task's request session
        log.debug('headers to add: %s' % config)
        if task.requests.headers:
            task.requests.headers.update(config)
        else:
            task.requests.headers = config


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHeaders, 'headers', api_ver=2)
