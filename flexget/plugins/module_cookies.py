import logging
import urllib2
import cookielib
from flexget.plugin import *

log = logging.getLogger('cookies')

class PluginCookies:
    """
        Adds cookie to all requests (rss, resolvers, download). Anything
        that uses urllib2 to be exact.
        
        Currently supports Firefox 3 cookies only.

        Example:

        cookies: /path/firefox/profile/something/cookies.sqlite
    """

    def validator(self,):
        from flexget import validator
        return validator.factory('file')

    def sqlite2cookie(self, filename):
        from cStringIO import StringIO
        try:
            from pysqlite2 import dbapi2 as sqlite
        except ImportError:
            raise PluginWarning('Unable to use pysqlite2', log)
 
        con = sqlite.connect(filename)
 
        cur = con.cursor()
        cur.execute('select host, path, isSecure, expiry, name, value from moz_cookies')
 
        ftstr = ['FALSE', 'TRUE']
 
        s = StringIO()
        s.write("""\
# Netscape HTTP Cookie File
# http://www.netscape.com/newsref/std/cookie_spec.html
# This is a generated file!  Do not edit.
""")
        count = 0
        for item in cur.fetchall():
            s.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (item[0], ftstr[item[0].startswith('.')], item[1],
                                                      ftstr[item[2]], item[3], item[4], item[5]))
            log.log(5, 'Adding cookie for %s. key: %s value: %s' % (item[0], item[4], item[5]))
            count += 1
            
        log.debug('Added %s cookies to jar' % count)
 
        s.seek(0)
        con.close()
 
        cookie_jar = cookielib.MozillaCookieJar()
        cookie_jar._really_load(s, '', True, True)
        return cookie_jar

    def feed_start(self, feed):
        """Feed starting, install cookiejar"""
        cj = self.sqlite2cookie(feed.config['cookies'])
        
        # create new opener for urllib2
        log.debug('Installing urllib2 opener')
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)
        
    def feed_abort(self, feed):
        """Feed aborted, unhook the cookiejar"""
        self.feed_exit(feed)

    def feed_exit(self, feed):
        """Feed exiting, remove cookiejar"""
        log.debug('Removing urllib2 opener')
        urllib2.install_opener(None)

register_plugin(PluginCookies, 'cookies')
