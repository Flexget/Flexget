from __future__ import unicode_literals, division, absolute_import
from builtins import object
from future.backports import urllib

import logging
import http.client
import socket

from flexget import plugin
from flexget.event import event

log = logging.getLogger('spy_headers')


class CustomHTTPConnection(http.client.HTTPConnection):

    def __init__(self, *args, **kwargs):
        http.client.HTTPConnection.__init__(self, *args, **kwargs)
        self.stored_headers = []

    def putheader(self, header, value):
        self.stored_headers.append((header, value))
        http.client.HTTPConnection.putheader(self, header, value)


class HTTPCaptureHeaderHandler(urllib.request.AbstractHTTPHandler):

    handler_order = 400

    def http_open(self, req):
        return self.do_open(CustomHTTPConnection, req)

    http_request = urllib.request.AbstractHTTPHandler.do_request_
    https_request = urllib.request.AbstractHTTPHandler.do_request_
    https_open = http_open

    def do_open(self, http_class, req):
        # All code here lifted directly from the python library
        host = req.get_host()
        if not host:
            from urllib.error import URLError
            raise URLError('no host given')

        h = http_class(host) # will parse host:port
        h.set_debuglevel(self._debuglevel)

        headers = dict(req.headers)
        headers.update(req.unredirected_hdrs)
        headers["Connection"] = "close"
        headers = dict(
            (name.title(), val) for name, val in list(headers.items()))
        try:
            h.request(req.get_method(), req.get_selector(), req.data, headers)
            r = h.getresponse()
        except socket.error as err: # XXX what error?
            raise urllib.error.URLError(err)
        r.recv = r.read
        fp = socket._fileobject(r, close=True)

        resp = urllib.request.addinfourl(fp, r.msg, req.get_full_url())
        resp.code = r.status
        resp.msg = r.reason

        # After this our custom code!
        req.all_sent_headers = h.stored_headers
        log.info('Request  : %s' % req.get_full_url())
        log.info('Response : %s (%s)' % (resp.code, resp.msg))

        # log headers
        log.info('-- Headers: --------------------------')
        for sh in h.stored_headers:
            log.info('%s: %s' % (sh[0], sh[1]))
        log.info('--------------------------------------')

        return resp


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
        # Backwards compatibility for plugins still using urllib
        if urllib.request._opener:
            log.debug('Adding HTTPCaptureHeaderHandler to default opener')
            urllib.request._opener.add_handler(HTTPCaptureHeaderHandler())
        else:
            log.debug('Creating new opener and installing it')
            opener = urllib.request.build_opener(HTTPCaptureHeaderHandler())
            urllib.request.install_opener(opener)

    def on_task_exit(self, task, config):
        """Task exiting, remove additions"""
        if not config:
            return
        task.requests.hooks['response'].remove(self.log_requests_headers)
        if urllib.request._opener:
            log.debug('Removing urllib2 default opener')
            # TODO: this uninstalls all other handlers as well, but does it matter?
            urllib.request.install_opener(None)

    # remove also on abort
    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSpyHeaders, 'spy_headers', api_ver=2)
