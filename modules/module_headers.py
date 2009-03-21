import logging
import urllib2
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('headers')

class HTTPHeadersProcessor(urllib2.BaseHandler):

    # run first
    handler_order = urllib2.HTTPHandler.handler_order - 10
 
    def __init__(self, headers={}):
        self.headers = headers

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

class ModuleHeaders:

    """
        Allow setting up any headers in all requests (which use urllib2)
        
        Example:
        
        headers:
          cookie: uid=<YOUR UID>; pass=<YOUR PASS>
    """

    def register(self, manager, parser):
        manager.register('headers')

    def validate(self, config):
        from validator import DictValidator
        root = DictValidator()
        root.accept_any_key(str)
        root.validate(config)
        return root.errors.messages

    def feed_start(self, feed):
        """Feed starting"""
        config = feed.config['headers']
        if urllib2._opener:
            log.debug('Adding HTTPCaptureHeaderHandler to default opener')
            urllib2._opener.add_handler(HTTPHeadersProcessor(config))
        else:
            log.debug('Creating new opener and installing it')
            opener = urllib2.build_opener(HTTPHeadersProcessor(config))
            urllib2.install_opener(opener)
        
    def feed_abort(self, feed):
        self.feed_exit(feed)

    def feed_exit(self, feed):
        """Feed exiting, remove additions"""
        if urllib2._opener:
            log.debug('Removing urllib2 default opener')
            # TODO: this uninstalls all other handlers as well, but does it matter?
            urllib2.install_opener(None)
