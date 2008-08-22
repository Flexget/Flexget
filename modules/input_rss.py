import logging
import urlparse
import urllib2
import xml.sax
import types
from feed import Entry
from manager import ModuleWarning

feedparser_present = True
try:
    import feedparser
except ImportError:
    feedparser_present = False

__pychecker__ = 'unusednames=parser'
 
log = logging.getLogger('rss')

class InputRSS:

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
        
        Incase RSS-feed uses some nonstandard field for urls (ie. guid) you can 
        configure module to use url from any feedparser entry attribute.
        
        Example:
        
        rss:
          url: <ul>
          link: guid
    """

    def register(self, manager, parser):
        manager.register('rss')

    def validate(self, config):
        """Validate given configuration"""
        from validator import DictValidator
        if isinstance(config, dict):
            rss = DictValidator()
            rss.accept('url', str, required=True)
            rss.accept('username', str)
            rss.accept('password', str)
            if config.has_key('username'):
                rss.require('password')
            rss.accept('link', str)
            rss.validate(config)
            return rss.errors.messages
        elif isinstance(config, str):
            return []
        else:
            return ['wrong datatype']

    def passwordize(self, url, user, password):
        """Add username and password to url"""
        parts = list(urlparse.urlsplit(url))
        parts[1] = user+':'+password+'@'+parts[1]
        url = urlparse.urlunsplit(parts)
        return url        

    def feed_input(self, feed):
        if not feedparser_present:
            raise ModuleWarning('Module RSS requires Feedparser. Please install it from http://www.feedparser.org/ or from your distro repository', log)

        config = feed.config['rss']
        if type(config) != types.DictType:
            config = {}
        url = feed.get_input_url('rss')

        # use basic auth when needed
        if config.has_key('username') and config.has_key('password'):
            url = self.passwordize(url, config['username'], config['password'])

        log.debug('Checking feed %s (%s)', feed.name, url)

        # check etags and last modified -headers
        etag = feed.cache.get('etag', None)
        if etag:
            log.debug('Sending etag %s for feed %s' % (etag, feed.name))
        modified = feed.cache.get('modified', None)
        if modified:
            log.debug('Sending last-modified %s for feed %s' % (etag, feed.name))

        # get the feed & parse
        try:
            rss = feedparser.parse(url, etag=etag, modified=modified)
        except IOError:
            raise Exception('IOError when loading feed %s', feed.name)

        # status checks
        status = rss.get('status', False)
        if status:
            if status == 304:
                log.debug('Feed %s hasn\'t changed, skipping' % feed.name)
                return
            elif status == 401:
                raise ModuleWarning('Authentication needed for feed %s: %s' % (feed.name, rss.headers['www-authenticate']), log)
            elif status == 404:
                raise ModuleWarning('RSS Feed %s not found' % feed.name, log)
            elif status == 500:
                raise ModuleWarning('Internal server exception on feed %s' % feed.name, log)
        else:
            log.error('rss does not have status: %s' % rss)
            
        # check for bozo
        ex = rss.get('bozo_exception', False)
        if ex:
            if ex == feedparser.NonXMLContentType:
                raise ModuleWarning('RSS Feed %s does not contain valid XML' % feed.name, log)
            elif ex == xml.sax._exceptions.SAXParseException:
                raise ModuleWarning('RSS Feed %s is not valid XML' % feed.name, log)
            elif ex == urllib2.URLError:
                raise ModuleWarning('urllib2.URLError', log)
            else:
                log.error('Unhandled bozo_exception. Type: %s.%s (feed: %s)' % (ex.__class__.__module__, ex.__class__.__name__ , feed.name))
                return

        if rss['bozo']:
            log.error(rss)
            log.error('Bozo feed exception on %s' % feed.name)
            return
            
        log.debug('encoding %s' % rss.encoding)

        # update etag, use last modified if no etag exists
        if rss.has_key('etag') and type(rss['etag']) != feedparser.types.NoneType:
            etag = rss.etag.replace("'", '').replace('"', '')
            feed.cache.store('etag', etag, 90)
            log.debug('etag %s saved for feed %s' % (etag, feed.name))
        elif rss.headers.has_key('last-modified'):
            feed.cache.store('modified', rss.modified, 90)
            log.debug('last modified saved for feed %s', feed.name)

        for entry in rss.entries:
            # skip rss items without links
            if not entry.has_key(config.get('link', 'link')):
                log.info('Skipped RSS-entry that does not contain configured link attribute %s' % config.get('link', 'link'))
                continue

            # fix for crap feeds with no ID
            if not entry.has_key('id'):
                entry['id'] = entry.link

            # add entry
            e = Entry()
            # field name for url can be configured by setting option link. 
            # default value is link but guid is used in some feeds
            try:
                e['url'] = getattr(entry, config.get('link', 'link'))
            except AttributeError, e:
                log.error('RSS-entry does not contain configured link attribute %s' % config.get('link', 'link'))
                continue
            e['title'] = entry.title.replace(u'\u200B', u'') # remove annoying zero width spaces

            # store basic auth info
            if config.has_key('username') and config.has_key('password'):
                e['basic_auth_username'] = config['username']
                e['basic_auth_password'] = config['password']
            
            feed.entries.append(e)
