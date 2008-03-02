import logging
import urllib2

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
        manager.register(instance=self, event='start', keyword='cookies', callback=self.start)
        manager.register(instance=self, event='exit', keyword='cookies', callback=self.exit)

    def start(self, feed):
        config = feed.config['cookies']
        if config.has_key('cookies'):
            # check that require configuration is present
            if not config['cookies'].has_key('type'):
                raise Warning('Cookies configuration is missing required field: type')
            if not config['cookie'].has_key('file'):
                raise Warning('Cookies configuration is missing required field: file')
            # create cookiejar
            import cookielib
            t = config['cookies']['type']
            if t == 'mozilla':
                cj = cookielib.MozillaCookieJar()
            elif t == 'lpw':
                cj = cookielib.LWPCookieJar()
            elif t == 'msie':
                cj = cookielib.MSIECookieJar()
            else:
                raise Warning('Unknown cookie type %s' % ctype)
            try:
                cj.load(filename=config['cookies']['file'], ignore_expires=True)
                log.debug('Cookies loaded')
            except (cookielib.LoadError, IOError), e:
                log.exception(e)
                raise Warning('Aborted feed because cookies could not be loaded.')
            # create new opener for urllib2
            log.debug('Removing urllib2 opener')
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
            urllib2.install_opener(opener)

    def exit(self, feed):
        log.debug('Removing urllib2 opener')
        urllib2.install_opener(None)
