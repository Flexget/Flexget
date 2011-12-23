import logging
import urllib2
from flexget.plugin import register_plugin, priority

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

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept_valid_keys('text', key_type='text')
        return config

    @priority(130)
    def on_feed_start(self, feed, config):
        """Feed starting"""
        # Set the headers for this feed's request session
        if feed.requests.headers:
            feed.requests.headers.update(config)
        else:
            feed.requests.headers = config
        # Set the headers in urllib2 for backwards compatibility
        if urllib2._opener:
            log.debug('Adding HTTPHeadersProcessor to default opener')
            urllib2._opener.add_handler(HTTPHeadersProcessor(config))
        else:
            log.debug('Creating new opener and installing it')
            opener = urllib2.build_opener(HTTPHeadersProcessor(config))
            urllib2.install_opener(opener)
        
    def on_feed_exit(self, feed, config):
        """Feed exiting, remove additions"""
        if urllib2._opener:
            log.debug('Removing urllib2 default opener')
            # TODO: this uninstalls all other handlers as well, but does it matter?
            urllib2.install_opener(None)
            
    on_feed_abort = on_feed_exit

register_plugin(PluginHeaders, 'headers', api_ver=2)
