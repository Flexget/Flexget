import logging
import urllib2
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('headers')

"""
class HTTHeadersPHandler(BaseHandler):

    def __init__(self):
        self.headers = {}

    def http_open(self, req):
        return self.do_open(httplib.HTTPConnection, req)
"""

class HTTPHeadersProcessor(urllib2.BaseHandler):

    # run first
    handler_order = urllib2.HTTPHandler.handler_order - 10
 
    def __init__(self, headers={}):
        self.headers = headers

    def http_request(self, request):
        for name, value in self.headers.iteritems():
            print repr(request)
            if not request.has_header(name):
                #print '***** adding header: %s = %s' % (name, value)
                request.add_unredirected_header(name, value)
        return request

    def http_response(self, request, response):
        return response

    https_request = http_request
    https_response = http_response

class ModuleHeaders:

    """
        Allow setting up any headers in all requests (using urllib2)
        
        Example:
        
        headers:
          Cookie: uid=<YOUR UID>, pass=<YOUR PASS>
    """

    def register(self, manager, parser):
        manager.register('headers')

    def validate(self, config):
        # TODO
        return []

    def feed_start(self, feed):
        """Feed starting, install cookiejar"""
        config = feed.config['headers']
        # create new opener for urllib2
        log.debug('Installing new urllib2 default opener')
        opener = urllib2.build_opener(HTTPHeadersProcessor(config))
        urllib2.install_opener(opener)
        
    def feed_abort(self, feed):
        """Feed aborted, unhook the cookiejar"""
        self.feed_exit(feed)

    def feed_exit(self, feed):
        """Feed exiting, remove cookiejar"""
        log.debug('Removing urllib2 default opener')
        urllib2.install_opener(None)
