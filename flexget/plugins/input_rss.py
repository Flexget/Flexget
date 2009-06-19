import logging
import urlparse
import xml.sax
import re
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.log import log_once

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
        
        You may wish to clean up the entry by stripping out all non-ascii characters. This can be done by
        setting ascii value to True.
        
        Example:
        
        rss:
          url: <url>
          ascii: True
        
        Incase RSS-feed uses some nonstandard field for urls and automatic detection fails 
        you can configure plugin to use url from any feedparser entry attribute.
        
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
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('url')
        advanced = root.accept('dict')
        url = advanced.accept('text', key='url', required=True) # TODO: accept only url, file
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('text', key='link')
        advanced.accept('boolean', key='silent')
        advanced.accept('boolean', key='ascii')
        return root

    def passwordize(self, url, user, password):
        """Add username and password to url"""
        parts = list(urlparse.urlsplit(url))
        parts[1] = user+':'+password+'@'+parts[1]
        url = urlparse.urlunsplit(parts)
        return url        

    def feed_input(self, feed):
        if not feedparser_present:
            raise PluginError('Plugin RSS requires Feedparser. Please install it from http://www.feedparser.org/ or from your distro repository', log)

        config = feed.config['rss']
        if not isinstance(config, dict):
            config = {}
        url = feed.get_input_url('rss')

        # use basic auth when needed
        if 'username' in config and 'password' in config:
            url = self.passwordize(url, config['username'], config['password'])

        log.debug('Checking feed %s (%s)', feed.name, url)

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

        # get the feed & parse
        try:
            rss = feedparser.parse(url, etag=etag, modified=modified)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise PluginError('Failed to reach server. Reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % e.code)

        # status checks
        status = rss.get('status', False)
        if status:
            if status == 304:
                log.debug('Feed %s hasn\'t changed, skipping' % feed.name)
                return
            elif status == 401:
                raise PluginError('Authentication needed for feed %s: %s' % (feed.name, rss.headers['www-authenticate']), log)
            elif status == 404:
                raise PluginError('RSS Feed %s not found' % feed.name, log)
            elif status == 500:
                raise PluginError('Internal server exception on feed %s' % feed.name, log)
        else:
            log.debug('RSS does not have status (normal if processing a file)')
            
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
                raise PluginWarning('RSS Feed %s is not valid XML' % feed.name, log)
            elif isinstance(ex, IOError):
                if hasattr(ex, 'reason'):
                    raise PluginError('Failed to reach server. Reason: %s' % ex.reason, log)
                elif hasattr(ex, 'code'):
                    raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % ex.code, log)
            else:
                raise PluginWarning('Unhandled bozo_exception. Type: %s.%s (feed: %s)' % \
                                    (ex.__class__.__plugin__, ex.__class__.__name__ , feed.name), log)

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
        curl = config.get('link', 'auto')
        ignored = 0
        for entry in rss.entries:

            # ignore entries without title            
            if not entry.title:
                log.debug('skipping entry without title')
                ignored += 1
                continue

            # ignore entries without link
            if not 'link' in entry and not 'enclosures' in entry:
                log.debug('%s does not have link or enclosure' % entry.title)
                ignored += 1
                continue
        
            # convert title to ascii (cleanup)
            if config.get('ascii', False):
                entry.title = entry.title.encode('ascii', 'ignore')
        
            # fix for crap feeds with no ID
            if not 'id' in entry:
                entry['id'] = entry.link

            # remove annoying zero width spaces
            entry.title = entry.title.replace(u'\u200B', u'') 

            # helper
            def add_entry(ea):
                from flexget.utils.tools import decode_html
                ea['title'] = entry.title
                if 'description' in entry:
                    ea['description'] = decode_html(entry.description)
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
                        ee['size'] = int(enclosure['length'])
                    if 'type' in enclosure: 
                        ee['type'] = enclosure['type']
                    # if enclosure has size OR there are multiple enclosures use filename from url
                    if ee.get('size', 0) != 0 or len(enclosures)>1:
                        if ee['url'].rfind != -1:
                            # parse filename from enclosure url
                            # TODO: better and perhaps join/in download plugin? also see urlparse module
                            match = re.search('.*\/([^?#]*)', ee['url'])
                            if match:
                                ee['filename'] = match.group(1)
                                #log.debug('filename %s from enclosure' % ee['filename'])
                    add_entry(ee)
                continue

            # create flexget entry
            e = Entry()
                
            # automaticly determine url from available fields
            if curl == 'auto':
                # try from link, guid
                if 'link' in entry:
                    e['url'] = entry['link']
                elif 'guid' in entry:
                    e['url'] = entry['guid']
                else:
                    if not config.get('silent'):
                        log_once('Failed to auto-detect RSS-entry %s link' % (entry.title), log)
                    ignored += 1    
                    continue
            else:
                # manual configuration
                if not 'curl' in entry:
                    log_once('RSS-entry %s does not contain configured link attributes: %s' % (entry.title, curl), log)
                    ignored += 1
                    continue
                e['url'] = getattr(entry, curl)
          
            add_entry(e)
            
        if ignored:
            if not config.get('silent'):
                log.warning('Skipped %s RSS-entries without required information (title, link or enclosures)' % ignored)

register_plugin(InputRSS, 'rss')
