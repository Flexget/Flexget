import http.cookiejar

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import TimedDict

logger = logger.bind(name='cookies')


class PluginCookies:
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
                    'type': {'type': 'string', 'enum': ['firefox3', 'mozilla', 'lwp']},
                },
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, str):
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
                raise plugin.PluginWarning('Unable to use sqlite3 or pysqlite2', logger)

        logger.debug('connecting: {}', filename)
        try:
            con = sqlite.connect(filename)
        except:
            raise plugin.PluginError('Unable to open cookies sqlite database')

        cur = con.cursor()
        try:
            cur.execute('select host, path, isSecure, expiry, name, value from moz_cookies')
        except sqlite.Error:
            raise plugin.PluginError(
                '%s does not appear to be a valid Firefox 3 cookies file' % filename, logger
            )

        ftstr = ['FALSE', 'TRUE']

        s = StringIO()
        s.write(
            """\
# Netscape HTTP Cookie File
# http://www.netscape.com/newsref/std/cookie_spec.html
# This is a generated file!  Do not edit.
"""
        )
        count = 0
        failed = 0

        logger.debug('fetching all cookies')

        def notabs(val):
            if isinstance(val, str):
                return val.replace('\t', '')
            return val

        while True:
            try:
                item = next(cur)
                # remove \t from item (#582)
                item = [notabs(field) for field in item]
                try:
                    s.write(
                        '%s\t%s\t%s\t%s\t%s\t%s\t%s\n'
                        % (
                            item[0],
                            ftstr[item[0].startswith('.')],
                            item[1],
                            ftstr[item[2]],
                            item[3],
                            item[4],
                            item[5],
                        )
                    )

                    logger.trace(
                        'Adding cookie for {}. key: {} value: {}', item[0], item[4], item[5]
                    )
                    count += 1
                except OSError:

                    def to_hex(x):
                        return ''.join([hex(ord(c))[2:].zfill(2) for c in x])

                    i = 0
                    for val in item:
                        if isinstance(val, str):
                            logger.debug('item[{}]: {}', i, to_hex(val))
                        else:
                            logger.debug('item[{}]: {}', i, val)
                        i += 1
                    failed += 1

            except UnicodeDecodeError:
                # for some god awful reason the sqlite module can throw UnicodeDecodeError ...
                logger.debug('got UnicodeDecodeError from sqlite, ignored')
                failed += 1
            except StopIteration:
                break

        logger.debug('Added {} cookies to jar. {} failed (non-ascii)', count, failed)

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
            logger.debug('Loading cookiejar from cache.')
        elif cookie_type == 'firefox3':
            logger.debug('Loading {} cookies', cookie_type)
            cj = self.sqlite2cookie(cookie_file)
            self.cookiejars[cookie_file] = cj
        else:
            if cookie_type == 'mozilla':
                logger.debug('Loading {} cookies', cookie_type)
                cj = http.cookiejar.MozillaCookieJar()
                self.cookiejars[cookie_file] = cj
            elif cookie_type == 'lwp':
                logger.debug('Loading {} cookies', cookie_type)
                cj = http.cookiejar.LWPCookieJar()
                self.cookiejars[cookie_file] = cj
            else:
                raise plugin.PluginError('Unknown cookie type %s' % cookie_type, logger)

            try:
                cj.load(filename=cookie_file, ignore_expires=True)
                logger.debug('{} cookies loaded', cookie_type)
            except (http.cookiejar.LoadError, OSError):
                import sys

                raise plugin.PluginError(
                    'Cookies could not be loaded: %s' % sys.exc_info()[1], logger
                )

        # Add cookiejar to our requests session
        task.requests.add_cookiejar(cj)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginCookies, 'cookies', api_ver=2)
