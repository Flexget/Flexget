import logging
import urlparse
import xml.sax
import re
import feedparser
import urllib2
import httplib
import socket
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.log import log_once
from flexget.plugins.cached_input import cached
from flexget.utils.tools import urlopener

log = logging.getLogger('rss')


class InputRSS(object):
    """
        Parses RSS feed.

        Hazzlefree configuration for public rss feeds:

        rss: <url>

        Configuration with basic http authentication:

        rss:
          url: <url>
          username: <name>
          password: <password>

        Advanced usages:

        You may wish to clean up the entry by stripping out all non-ascii characters.
        This can be done by setting ascii value to yes.

        Example:

        rss:
          url: <url>
          ascii: yes

        Incase RSS-feed uses some nonstandard field for urls and automatic detection fails
        you can configure plugin to use url from any feedparser entry attribute.

        Example:

        rss:
          url: <url>
          link: guid

        You can disable few possibly annoying warnings by setting silent value to
        yes on feeds where there are frequently invalid items.

        Example:

        rss:
          url: <url>
          silent: yes
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('url')
        root.accept('file')
        advanced = root.accept('dict')
        advanced.accept('url', key='url', required=True)
        advanced.accept('file', key='url')
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('text', key='link')
        advanced.accept('list', key='link').accept('text')
        advanced.accept('boolean', key='silent')
        advanced.accept('boolean', key='ascii')
        advanced.accept('boolean', key='filename')
        return root

    def get_config(self, feed):
        config = feed.config['rss']
        if isinstance(config, basestring):
            config = {'url': config}
        if isinstance(config.get('link'), basestring):
            config['link'] = [config['link']]
        if config.get('link'):
            config['link'] = [link.lower() for link in config['link']]
        # set the default link fields to 'link' and 'guid'
        if not config.get('link') or 'auto' in config['link']:
            config['link'] = ['link', 'guid']
        # use basic auth when needed
        if 'username' in config and 'password' in config:
            config['url'] = self.passwordize(config['url'], config['username'], config['password'])
        return config

    def passwordize(self, url, user, password):
        """Add username and password to url"""
        parts = list(urlparse.urlsplit(url))
        parts[1] = user + ':' + password + '@' + parts[1]
        url = urlparse.urlunsplit(parts)
        return url

    @cached('rss', 'url')
    @internet(log)
    def on_feed_input(self, feed):
        config = self.get_config(feed)

        log.debug('Checking feed %s (%s)' % (feed.name, config['url']))

        # check etags and last modified -headers
        # let's not, flexget works better when feed contains all entries all the time ?
        etag = None
        modified = None
        """
        etag = feed.cache.get('etag', None)
        if etag:
            log.debug('Sending etag %s for feed %s' % (etag, feed.name))
        modified = feed.cache.get('modified', None)
        if modified:
            log.debug('Sending last-modified %s for feed %s' % (etag, feed.name))
        """

        # set timeout to one minute
        orig_timout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(60)

        # get the feed & parse
        if urllib2._opener:
            rss = feedparser.parse(config['url'], etag=etag, modified=modified, handlers=urllib2._opener.handlers)
        else:
            rss = feedparser.parse(config['url'], etag=etag, modified=modified)

        # restore original timeout
        socket.setdefaulttimeout(orig_timout)

        # status checks
        status = rss.get('status', False)
        if not status:
            log.debug('RSS does not have status (normal if processing a file)')
        elif status == 304:
            log.debug('Feed %s hasn\'t changed, skipping' % feed.name)
            return
        elif status == 401:
            raise PluginError('Authentication needed for feed %s: %s' % \
                (feed.name, rss.headers['www-authenticate']), log)
        elif status == 404:
            raise PluginError('RSS Feed %s not found' % feed.name, log)
        elif status == 500:
            raise PluginError('Internal server exception on feed %s' % feed.name, log)

        # check for bozo
        ex = rss.get('bozo_exception', False)
        ignore = False
        if ex:
            if isinstance(ex, feedparser.NonXMLContentType):
                # see: http://www.feedparser.org/docs/character-encoding.html#advanced.encoding.nonxml
                log.debug('ignoring feedparser.NonXMLContentType')
                ignore = True
            elif isinstance(ex, feedparser.CharacterEncodingOverride):
                # see: ticket 88
                log.debug('ignoring feedparser.CharacterEncodingOverride')
                ignore = True
            elif isinstance(ex, xml.sax._exceptions.SAXParseException):
                if len(rss.entries) == 0:
                    # save invalid data for review, this is a bit ugly but users seem to really confused when
                    # html pages (login pages) are received
                    log.critical('Invalid XML received from feed %s' % feed.name)
                    req = urlopener(config['url'], log)
                    data = req.read()
                    req.close()
                    ext = 'xml'
                    if '<html>' in data.lower():
                        log.critical('Received content is HTML page, not an RSS feed')
                        ext = 'html'
                    if 'login' in data.lower() or 'username' in data.lower():
                        log.critical('Received content looks a bit like login page')
                    if 'error' in data.lower():
                        log.critical('Received content looks a bit like error page')
                    import os
                    received = os.path.join(feed.manager.config_base, 'received')
                    if not os.path.isdir(received):
                        os.mkdir(received)
                    filename = os.path.join(received, '%s.%s' % (feed.name, ext))
                    f = open(filename, 'w')
                    f.write(data)
                    f.close()
                    log.critical('I have saved the invalid content to %s for you to view' % filename)
                    raise PluginError('Received invalid RSS content')
                else:
                    msg = 'Invalid XML received. However feedparser still produced entries. Ignoring the error ...'
                    if not config.get('silent', False):
                        log.info(msg)
                    else:
                        log.debug(msg)
                    ignore = True
            elif isinstance(ex, httplib.BadStatusLine) or \
                 isinstance(ex, IOError):
                raise ex # let the @internet decorator handle
            else:
                # all other bozo errors
                # TODO: refactor the dumping into a own method, DUPLICATED CODE
                if len(rss.entries) == 0:
                    log.critical('Invalid RSS received from feed %s' % feed.name)
                    req = urlopener(config['url'], log)
                    data = req.read()
                    req.close()
                    ext = 'xml'
                    import os
                    received = os.path.join(feed.manager.config_base, 'received')
                    if not os.path.isdir(received):
                        os.mkdir(received)
                    filename = os.path.join(received, '%s.%s' % (feed.name, ext))
                    f = open(filename, 'w')
                    f.write(data)
                    f.close()
                    log.critical('I have saved the invalid content to %s for you to view' % filename)
                    raise PluginError('Unhandled bozo_exception. Type: %s (feed: %s)' % \
                        (ex.__class__.__name__, feed.name), log)
                else:
                    msg = 'Invalid RSS received. However feedparser still produced entries. Ignoring the error ...'
                    if not config.get('silent', False):
                        log.info(msg)
                    else:
                        log.debug(msg)

        if rss['bozo'] and not ignore:
            log.error(rss)
            log.error('Bozo feed exception on %s' % feed.name)
            return

        log.debug('encoding %s' % rss.encoding)

        # update etag, use last modified if no etag exists
        """
        if 'etag' in rss and type(rss['etag']) != feedparser.types.NoneType:
            etag = rss.etag.replace("'", '').replace('"', '')
            feed.cache.store('etag', etag, 90)
            log.debug('etag %s saved for feed %s' % (etag, feed.name))
        elif hasattr(rss, 'headers'):
            if 'last-modified' in rss.headers:
                feed.cache.store('modified', rss.modified, 90)
                log.debug('last modified saved for feed %s', feed.name)
        """

        # field name for url can be configured by setting link.
        # default value is auto but for example guid is used in some feeds
        ignored = 0
        for entry in rss.entries:

            # ignore entries without title
            if not entry.title:
                log.debug('skipping entry without title')
                ignored += 1
                continue

            # convert title to ascii (cleanup)
            if config.get('ascii', False):
                entry.title = entry.title.encode('ascii', 'ignore')

            # remove annoying zero width spaces
            entry.title = entry.title.replace(u'\u200B', u'')

            # helper
            # TODO: confusing? refactor into class member ...

            def add_entry(ea):
                from flexget.utils.tools import decode_html
                ea['title'] = entry.title

                # grab fields
                fields = ['author', 'description']
                for field in fields:
                    if field in entry:
                        try:
                            ea[field] = decode_html(getattr(entry, field))
                        except UnicodeDecodeError:
                            log.warning('Failed to decode entry %s field %s' % (ea['title'], field))

                # store basic auth info
                if 'username' in config and 'password' in config:
                    ea['basic_auth_username'] = config['username']
                    ea['basic_auth_password'] = config['password']
                feed.entries.append(ea)

            # create from enclosures if present
            enclosures = entry.get('enclosures', [])
            if enclosures:
                #log.debug('adding %i entries from enclosures' % len(enclosures))
                for enclosure in enclosures:
                    ee = Entry()
                    if not 'href' in enclosure:
                        log_once('RSS-entry %s enclosure does not have url' % entry.title, log)
                        continue
                    ee['url'] = enclosure['href']
                    # get optional meta-data
                    if 'length' in enclosure:
                        try:
                            ee['size'] = int(enclosure['length'])
                        except:
                            ee['size'] = 0
                    if 'type' in enclosure:
                        ee['type'] = enclosure['type']
                    # if enclosure has size OR there are multiple enclosures use filename from url
                    if ee.get('size', 0) != 0 or len(enclosures) > 1:
                        if ee['url'].rfind != -1:
                            # parse filename from enclosure url
                            # TODO: better and perhaps join/in download plugin? also see urlparse module
                            match = re.search('.*\/([^?#]*)', ee['url'])
                            if match and config.get('filename', True):
                                ee['filename'] = match.group(1)
                                log.log(5, 'filename %s from enclosure' % ee['filename'])
                    add_entry(ee)
                continue

            # create flexget entry
            e = Entry()

            # search for known url fields
            for url_field in config['link']:
                if url_field in entry:
                    e['url'] = entry[url_field]
                    break
            else:
                log.debug('%s does not have link (%s) or enclosure' % (entry.title, ', '.join(config['link'])))
                ignored += 1
                continue

            add_entry(e)

        if ignored:
            if not config.get('silent'):
                log.warning('Skipped %s RSS-entries without required information (title, link or enclosures)' % ignored)

register_plugin(InputRSS, 'rss')
