import logging
import urlparse
import urllib
import urllib2
import xml.sax
import re

try:
    import feedparser
except ImportError:
    print "Please install Feedparser from http://www.feedparser.org/ or from your distro repository"
    import sys
    sys.exit(1)

log = logging.getLogger('rss')

class InputRSS:

    """
        Parses RSS feed.

        Short configuration:

        rss: <url>

        Configuration with authentication parameters:

        rss:
          url: <url>
          username: <name>
          password: <password>
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

        config = feed.config
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
                raise Exception("Authentication needed for feed %s: %s", feed.name, rss.headers['www-authenticate'])
            elif rss.status == 404:
                raise Exception("Feed %s not found", feed.name)
            elif rss.status == 500:
                raise Exception("Internal server exception on feed %s", feed.name)
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

            # Fixes for "interesting" feed structures
            # TODO: these should be fixed in separate module !
            if entry.link.startswith("http://www.mininova.org/tor/"):
                entry.link = entry.link.replace('tor', 'get')
            elif entry.link.startswith("http://www.torrentspy.com/torrent/"):
                m = re.match("http://www.torrentspy.com/torrent/([\d]+)/", entry.link)
                torrent_id = m.group(1)
                entry.link = "http://www.torrentspy.com/download.asp?id=%s" % torrent_id

            # Use basic auth when needed
            if config.has_key('username') and config.has_key('password'):
                log.debug("Using basic auth for retrieval")
                entry.link = self.passwordize(entry.link, config['username'], config['password'])

            # add entry
            e = {}
            e['url'] = entry.link.encode()
            e['title'] = entry.title.replace(u"\u200B", u"") # remove annoying zero width spaces
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
