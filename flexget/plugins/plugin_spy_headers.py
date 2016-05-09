from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('spy_headers')


class PluginSpyHeaders(object):
    """
        Logs all headers sent in http requests. Useful for resolving issues.

        WARNING: At the moment this modifies requests somehow!
    """

    schema = {'type': 'boolean'}

    @staticmethod
    def log_requests_headers(response, **kwargs):
        log.info('Request  : %s' % response.request.url)
        log.info('Response : %s (%s)' % (response.status_code, response.reason))
        log.info('-- Headers: --------------------------')
        for header, value in response.request.headers.items():
            log.info('%s: %s' % (header, value))
        log.info('--------------------------------------')
        return response

    def on_task_start(self, task, config):
        if not config:
            return
        # Add our hook to the requests session
        task.requests.hooks['response'].append(self.log_requests_headers)

    def on_task_exit(self, task, config):
        """Task exiting, remove additions"""
        if not config:
            return
        task.requests.hooks['response'].remove(self.log_requests_headers)

    # remove also on abort
    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSpyHeaders, 'spy_headers', api_ver=2)
