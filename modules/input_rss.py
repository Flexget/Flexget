import logging
import urlparse
import urllib2
import xml.sax
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
        
        You may wish to clean up the entry by stripping out all non-ascii characters. This can be done by
        setting ascii value to True.
        
        Example:
        
        rss:
          url: <url>
          ascii: True
        
        Incase RSS-feed uses some nonstandard field for urls and automatic detection fails 
        you can configure module to use url from any feedparser entry attribute.
        
        Example:
        
        rss:
          url: <url>
          link: guid
          
        You can disable few possibly annoying warnings by setting silent value to True on feeds where there are 
        frequently invalid items.
       
        Example:
       
        rss:
          url: <url>
          silent: True
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
            rss.accept('silent', bool)
            if config.has_key('username'):
                rss.require('password')
            rss.accept('link', str)
            rss.accept('ascii', bool)
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
        if not isinstance(config, dict):
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
                raise ModuleWarning('RSS Feed %s is not valid XML' % feed.name, log)
            elif isinstance(ex, urllib2.URLError):
                raise ModuleWarning('urllib2.URLError', log)
            else:
                raise ModuleWarning('Unhandled bozo_exception. Type: %s.%s (feed: %s)' % (ex.__class__.__module__, ex.__class__.__name__ , feed.name), log)

        if rss['bozo'] and not ignore:
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

        # field name for url can be configured by setting link. 
        # default value is auto but for example guid is used in some feeds
        curl = config.get('link', 'auto')
        for entry in rss.entries:
            # convert title to ascii (cleanup)
            if config.get('ascii', False):
                entry.title = entry.title.encode('ascii', 'ignore')
        
            # fix for crap feeds with no ID
            if not entry.has_key('id'):
                entry['id'] = entry.link

            # remove annoying zero width spaces
            entry.title = entry.title.replace(u'\u200B', u'') 

            # ignore entries without title            
            if not entry.title:
                log.debug('skipping entry without title')
                continue

            # helper
            def add_entry(ea):
                ea['title'] = entry.title
                if entry.has_key('description'):
                    # TODO: html decode!
                    ea['description'] = entry.description
                # store basic auth info
                if config.has_key('username') and config.has_key('password'):
                    ea['basic_auth_username'] = config['username']
                    ea['basic_auth_password'] = config['password']
                feed.entries.append(ea)
                
            # create from enclosures if present
            enclosures = entry.get('enclosures', [])
            if enclosures:
                log.debug('adding %i entries from enclosures' % len(enclosures))
                for enclosure in enclosures:
                    ee = Entry()
                    if not enclosure.has_key('href'):
                        feed.log_once('RSS-entry %s enclosure does not have url' % entry.title, log)
                        continue
                    ee['url'] = enclosure['href']
                    # get optional meta-data
                    if enclosure.has_key('length'): ee['size'] = int(enclosure['length'])
                    if enclosure.has_key('type'): ee['type'] = enclosure['type']
                    # if enclosure has size OR there are multiple enclosures use filename from url
                    if ee.get('size', 0) != 0 or len(enclosures)>1:
                        if ee['url'].rfind != -1:
                            ee['filename'] = ee['url'][ee['url'].rfind('/')+1:]
                            log.debug('filename %s from enclosure' % ee['filename'])
                    add_entry(ee)
                continue

            # create flexget entry
            e = Entry()
                
            # automaticly determine url from available fields
            if curl == 'auto':
                # try from link, guid
                if entry.has_key('link'):
                    e['url'] = entry['link']
                elif entry.has_key('guid'):
                    e['url'] = entry['guid']
                else:
                    if not config.get('silent'):
                        feed.log_once('Failed to auto-detect RSS-entry %s link' % (entry.title), log)
                    continue
            else:
                # manual configuration
                if not entry.has_key(curl):
                    feed.log_once('RSS-entry %s does not contain configured link attributes: %s' % (entry.title, curl), log)
                    continue
                e['url'] = getattr(entry, curl)
          
            add_entry(e)