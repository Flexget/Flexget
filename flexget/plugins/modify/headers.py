from __future__ import unicode_literals, division, absolute_import
import logging
import urllib2

from flexget import plugin
from flexget.event import event

log = logging.getLogger('headers')


class HTTPHeadersProcessor(urllib2.BaseHandler):

    # run first
    handler_order = urllib2.HTTPHandler.handler_order - 10

    def __init__(self, headers=None):
        if headers:
            self.headers = headers
        else:
            self.headers = {}

    def http_request(self, request):
        for name, value in self.headers.iteritems():
            if not request.has_header(name):
                log.debug('Adding %s: %s' % (name, value))
                request.add_unredirected_header(name.capitalize(), value.strip())
            else:
                log.debug('Header "%s" exists with value "%s"' % (name, request.get_header(name)))
        return request

    def http_response(self, request, response):
        return response

    https_request = http_request
    https_response = http_response


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
        # Set the headers in urllib2 for backwards compatibility
        if urllib2._opener:
            log.debug('Adding HTTPHeadersProcessor to default opener')
            urllib2._opener.add_handler(HTTPHeadersProcessor(config))
        else:
            log.debug('Creating new opener and installing it')
            opener = urllib2.build_opener(HTTPHeadersProcessor(config))
            urllib2.install_opener(opener)

    def on_task_exit(self, task, config):
        """Task exiting, remove additions"""
        if urllib2._opener:
            log.debug('Removing urllib2 default opener')
            # TODO: this uninstalls all other handlers as well, but does it matter?
            urllib2.install_opener(None)

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHeaders, 'headers', api_ver=2)
