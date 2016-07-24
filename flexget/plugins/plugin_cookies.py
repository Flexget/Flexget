from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
import http.cookiejar

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import TimedDict

log = logging.getLogger('cookies')


class PluginCookies(object):
    """
    Adds cookie to all requests (rss, resolvers, download). Anything
    that uses urllib2 to be exact.

    Currently supports Firefox 3 cookies only.

    Example::

      cookies: /path/firefox/profile/something/cookies.sqlite
    """

    # TODO: 1.2 Is this a good way to handle this? How long should the time be?
    # Keeps loaded cookiejars cached for some time
    cookiejars = TimedDict(cache_time='5 minutes')

    schema = {
        'oneOf': [
            {'type': 'string', 'format': 'file'},
            {
                'type': 'object',
                'properties': {
                    'file': {'type': 'string', 'format': 'file'},
                    'type': {'type': 'string', 'enum': ['firefox3', 'mozilla', 'lwp']}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, basestring):
            config = {'file': config}
        if config['file'].endswith('.txt'):
            config.setdefault('type', 'mozilla')
        elif config['file'].endswith('.lwp'):
            config.setdefault('type', 'lwp')
        else:
            config.setdefault('type', 'firefox3')
        return config

    def sqlite2cookie(self, filename):
        from io import StringIO
        try:
            from pysqlite2 import dbapi2 as sqlite
        except ImportError:
            try:
                from sqlite3 import dbapi2 as sqlite  # try the 2.5+ stdlib
            except ImportError:
                raise plugin.PluginWarning('Unable to use sqlite3 or pysqlite2', log)

        log.debug('connecting: %s' % filename)
        try:
            con = sqlite.connect(filename)
        except:
            raise plugin.PluginError('Unable to open cookies sqlite database')

        cur = con.cursor()
        try:
            cur.execute('select host, path, isSecure, expiry, name, value from moz_cookies')
        except sqlite.Error:
            raise plugin.PluginError('%s does not appear to be a valid Firefox 3 cookies file' % filename, log)

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

        def notabs(val):
            if isinstance(val, basestring):
                return val.replace('\t', '')
            return val

        while True:
            try:
                item = next(cur)
                # remove \t from item (#582)
                item = [notabs(field) for field in item]
                try:
                    s.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (item[0], ftstr[item[0].startswith('.')], item[1],
                                                              ftstr[item[2]], item[3], item[4], item[5]))

                    log.trace('Adding cookie for %s. key: %s value: %s' % (item[0], item[4], item[5]))
                    count += 1
                except IOError:
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

        cookie_jar = http.cookiejar.MozillaCookieJar()
        cookie_jar._really_load(s, '', True, True)
        return cookie_jar

    def on_task_start(self, task, config):
        """Task starting, install cookiejar"""
        import os
        config = self.prepare_config(config)
        cookie_type = config.get('type')
        cookie_file = os.path.expanduser(config.get('file'))
        cj = self.cookiejars.get(cookie_file, None)
        if cj is not None:
            log.debug('Loading cookiejar from cache.')
        elif cookie_type == 'firefox3':
            log.debug('Loading %s cookies' % cookie_type)
            cj = self.sqlite2cookie(cookie_file)
            self.cookiejars[cookie_file] = cj
        else:
            if cookie_type == 'mozilla':
                log.debug('Loading %s cookies' % cookie_type)
                cj = http.cookiejar.MozillaCookieJar()
                self.cookiejars[cookie_file] = cj
            elif cookie_type == 'lwp':
                log.debug('Loading %s cookies' % cookie_type)
                cj = http.cookiejar.LWPCookieJar()
                self.cookiejars[cookie_file] = cj
            else:
                raise plugin.PluginError('Unknown cookie type %s' % cookie_type, log)

            try:
                cj.load(filename=cookie_file, ignore_expires=True)
                log.debug('%s cookies loaded' % cookie_type)
            except (http.cookiejar.LoadError, IOError):
                import sys
                raise plugin.PluginError('Cookies could not be loaded: %s' % sys.exc_info()[1], log)

        # Add cookiejar to our requests session
        task.requests.add_cookiejar(cj)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginCookies, 'cookies', api_ver=2)
