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

    def validator(self):
        from flexget import validator
        return validator.factory('file')

    def sqlite2cookie(self, filename):
        from cStringIO import StringIO
        try:
            from pysqlite2 import dbapi2 as sqlite
        except ImportError:
            try:
                from sqlite3 import dbapi2 as sqlite # try the 2.5+ stdlib
            except ImportError:
                raise PluginWarning('Unable to use sqlite3 or pysqlite2', log)

        log.debug('connecting: %s' % filename)
        try:
            con = sqlite.connect(filename)
        except:
            raise PluginError('Unable to open cookies sqlite database')
 
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
        failed = 0

        log.debug('fetching all cookies')

        while True:
            try:
                item = cur.next()
                # remove \t from item (#582)
                item = [si.replace('\t', '') for si in item]
                try:
                    s.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (item[0], ftstr[item[0].startswith('.')], item[1],
                                                              ftstr[item[2]], item[3], item[4], item[5]))

                    log.log(5, 'Adding cookie for %s. key: %s value: %s' % (item[0], item[4], item[5]))
                    count += 1
                except:
                    to_hex = lambda x: ''.join([hex(ord(c))[2:].zfill(2) for c in x])
                    i = 0
                    for val in item:
                        if isinstance(val, basestring):
                            log.debug('item[%s]: %s' % (i, to_hex(val)))
                        else:
                            log.debug('item[%s]: %s' % (i, val))
                        i += 1
                    failed += 1

            except UnicodeDecodeError:
                # for some god awful reason the sqlite module can throw UnicodeDecodeError ...
                log.debug('got UnicodeDecodeError from sqlite, ignored')
                failed += 1
            except StopIteration:
                break

        log.debug('Added %s cookies to jar. %s failed (non-ascii)' % (count, failed))
 
        s.seek(0)
        con.close()
 
        cookie_jar = cookielib.MozillaCookieJar()
        cookie_jar._really_load(s, '', True, True)
        return cookie_jar

    def on_feed_start(self, feed):
        import os
        """Feed starting, install cookiejar"""
        cj = self.sqlite2cookie(os.path.expanduser(feed.config['cookies']))
        
        # create new opener for urllib2
        log.debug('Installing urllib2 opener')
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)
        
    def on_feed_exit(self, feed):
        """Feed exiting, remove cookiejar"""
        log.debug('Removing urllib2 opener')
        urllib2.install_opener(None)
        
    # Feed aborted, unhook the cookiejar
    on_feed_abort = on_feed_exit

register_plugin(PluginCookies, 'cookies')
