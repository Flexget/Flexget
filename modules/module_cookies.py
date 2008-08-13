import logging
import urllib2

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('cookies')

class ModuleCookies:

    """
        Adds cookie to all requests (rss, resolvers, download). Anything
        that uses urllib2 to be exact.

        Configuration:

        cookies:
          type: mozilla
          file: /path/to/cookie

        Possible cookie types are: mozilla, msie, lpw
    """

    def register(self, manager, parser):
        manager.register('cookies')

    def validate(self, config):
        from validator import DictValidator
        cookies = DictValidator()
        cookies.accept('type', ['mozilla', 'msie', 'lpw'], required=True)
        cookies.accept('file', str, required=True)
        cookies.validate(config) 
        return cookies.errors.messages

    def feed_start(self, feed):
        """Feed starting, install cookiejar"""
        config = feed.config['cookies']
        # check that require configuration is present
        if not config.has_key('type'):
            raise Warning('Cookies configuration is missing required field: type')
        if not config.has_key('file'):
            raise Warning('Cookies configuration is missing required field: file')
        # create cookiejar
        import cookielib
        t = config['type']
        if t == 'mozilla':
            cj = cookielib.MozillaCookieJar()
        elif t == 'lpw':
            cj = cookielib.LWPCookieJar()
        elif t == 'msie':
            cj = cookielib.MSIECookieJar()
        else:
            raise Warning('Unknown cookie type %s' % t)
        try:
            cj.load(filename=config['file'], ignore_expires=True)
            log.debug('Cookies loaded')
        except (cookielib.LoadError, IOError):
            import sys
            raise Warning('Cookies could not be loaded: %s' % sys.exc_info()[1])
        # create new opener for urllib2
        log.debug('Installing urllib2 opener')
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)

    def feed_exit(self, feed):
        """Feed exiting, remove cookiejar"""
        log.debug('Removing urllib2 opener')
        urllib2.install_opener(None)
