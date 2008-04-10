import logging
import urlparse
import urllib
import urllib2
import xml.sax
import re
import types
from feed import Entry

feedparser_present = True
try:
    import feedparser
except ImportError:
    feedparser_present = False

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
        manager.register(instance=self, event="input", keyword="rss", callback=self.run)

    def passwordize(self, url, user, password):
        """Add username and password to url"""
        parts = list(urlparse.urlsplit(url))
        parts[1] = user+":"+password+"@"+parts[1]
        url = urlparse.urlunsplit(parts)
        return url        

    def run(self, feed):
        if not feedparser_present:
            raise Warning("Module RSS requires Feedparser. Please install it from http://www.feedparser.org/ or from your distro repository")

        config = feed.config['rss']
        if type(config) != types.DictType:
            config = {}
        url = feed.get_input_url('rss')

        # use basic auth when needed
        if config.has_key('username') and config.has_key('password'):
            url = self.passwordize(url, config['username'], config['password'])

        log.debug("Checking feed %s (%s)", feed.name, url)

        # check etags and last modified -headers
        etag = feed.cache.get('etag', None)
        if etag:
            log.debug("Sending etag %s for feed %s" % (etag, feed.name))
        modified = feed.cache.get('modified', None)
        if modified:
            log.debug("Sending last-modified %s for feed %s" % (etag, feed.name))

        # get the feed & parse
        try:
            rss = feedparser.parse(url, etag=etag, modified=modified)
        except IOError:
            raise Exception("IOError when loading feed %s", feed.name)

        try:
            # status checks
            if rss.status == 304:
                log.debug("Feed %s hasn't changed, skipping" % feed.name)
                return
            elif rss.status == 401:
                raise Warning("Authentication needed for feed %s: %s", feed.name, rss.headers['www-authenticate'])
            elif rss.status == 404:
                raise Warning("Feed %s not found", feed.name)
            elif rss.status == 500:
                raise Warning("Internal server exception on feed %s", feed.name)
        except urllib2.URLError:
            raise Exception("URLError on feed %s", feed.name)
        except AttributeError, e:
            ex = rss['bozo_exception']
            if ex == feedparser.NonXMLContentType:
                log.error("feedparser.NonXMLContentType")
                return
            elif ex == xml.sax._exceptions.SAXParseException:
                log.error("xml.sax._exceptions.SAXParseException")
                return
            elif ex == urllib2.URLError:
                log.error("urllib2.URLError")
                return
            else:
                log.error("Unhandled bozo_exception. Type: %s.%s (feed: %s)" % (ex.__class__.__module__, ex.__class__.__name__ , feed.name))
                return

        if rss['bozo']:
            log.error(rss)
            log.error("Bozo feed exception on %s. Is the URL correct?" % feed.name)
            return
            
        log.debug('encoding %s' % rss.encoding)

        # update etag, use last modified if no etag exists
        if rss.has_key('etag') and type(rss['etag']) != feedparser.types.NoneType:
            etag = rss.etag.replace("'", "").replace('"', "")
            feed.cache.store('etag', etag, 90)
            log.debug("etag %s saved for feed %s" % (etag, feed.name))
        elif rss.headers.has_key('last-modified'):
            feed.cache.store('modified', rss.modified, 90)
            log.debug("last modified saved for feed %s", feed.name)

        for entry in rss.entries:
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
            e['title'] = entry.title.replace(u"\u200B", u"") # remove annoying zero width spaces

            # store basic auth info
            if config.has_key('username') and config.has_key('password'):
                e['basic_auth_username'] = config['username']
                e['basic_auth_password'] = config['password']
            
            feed.entries.append(e)

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

    from test_tools import MockFeed
    feed = MockFeed()

    rss = InputRSS()
    rss.run(feed)

    import yaml
    print yaml.dump(feed.entries)
