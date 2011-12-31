import os
import logging
import urlparse
import xml.sax
import posixpath
import httplib
from datetime import datetime
import feedparser
from requests import RequestException
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet, PluginError, get_plugin_by_name, DependencyError
from flexget.utils.cached_input import cached
from flexget.utils.tools import decode_html

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

        In case RSS-feed uses some nonstandard field for urls and automatic detection fails
        you can configure plugin to use url from any feedparser entry attribute.

        Example:

        rss:
          url: <url>
          link: guid

        If you want to keep information in another rss field attached to the flexget entry, you can use the other_fields option.

        Example:

        rss:
          url: <url>
          other_fields: [date]

        You can disable few possibly annoying warnings by setting silent value to
        yes on feeds where there are frequently invalid items.

        Example:

        rss:
          url: <url>
          silent: yes

        You can group all the links of an item, to make the download plugin tolerant
        to broken urls: it will try to download each url until one works.
        Links are enclosures plus item fields given by the link value, in that order.
        The value to set is "group_links".

        Example:

        rss:
          url: <url>
          group_links: yes
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
        advanced.accept('text', key='title')
        advanced.accept('text', key='link')
        advanced.accept('list', key='link').accept('text')
        advanced.accept('list', key='other_fields').accept('text')
        advanced.accept('boolean', key='silent')
        advanced.accept('boolean', key='ascii')
        advanced.accept('boolean', key='filename')
        advanced.accept('boolean', key='group_links')
        advanced.accept('boolean', key='etag')
        return root

    def build_config(self, config):
        """Set default values to config"""
        if isinstance(config, basestring):
            config = {'url': config}
        # set the default link value to 'auto'
        config.setdefault('link', 'auto')
        # Replace : with _ and lower case other fields so they can be found in rss
        if config.get('other_fields'):
            config['other_fields'] = [field.replace(':', '_').lower() for field in config['other_fields']]
        # set default value for group_links as deactivated
        config.setdefault('group_links', False)
        # set default for etag
        config.setdefault('etag', True)
        return config

    def process_invalid_content(self, feed, data):
        """If feedparser reports error, save the received data and log error."""

        ext = 'xml'
        if '<html>' in data.lower():
            log.critical('Received content is HTML page, not an RSS feed')
            ext = 'html'
        if 'login' in data.lower() or 'username' in data.lower():
            log.critical('Received content looks a bit like login page')
        if 'error' in data.lower():
            log.critical('Received content looks a bit like error page')
        received = os.path.join(feed.manager.config_base, 'received')
        if not os.path.isdir(received):
            os.mkdir(received)
        filename = os.path.join(received, '%s.%s' % (feed.name, ext))
        f = open(filename, 'w')
        f.write(data)
        f.close()
        log.critical('I have saved the invalid content to %s for you to view' % filename)

    def add_enclosure_info(self, entry, enclosure, filename=True, multiple=False):
        """Stores information from an rss enclosure into an Entry."""
        entry['url'] = enclosure['href']
        # get optional meta-data
        if 'length' in enclosure:
            try:
                entry['size'] = int(enclosure['length'])
            except:
                entry['size'] = 0
        if 'type' in enclosure:
            entry['type'] = enclosure['type']
        # TODO: better and perhaps join/in download plugin?
        # Parse filename from enclosure url
        basename = posixpath.basename(urlparse.urlsplit(entry['url']).path)
        # If enclosure has size OR there are multiple enclosures use filename from url
        if (entry.get('size') or multiple and basename) and filename:
            entry['filename'] = basename
            log.trace('filename `%s` from enclosure' % entry['filename'])

    @cached('rss')
    @internet(log)
    def on_feed_input(self, feed, config):
        config = self.build_config(config)

        log.debug('Requesting feed `%s` url `%s`' % (feed.name, config['url']))

        # Used to identify which etag/modified to use
        url_hash = str(hash(config['url']))

        # set etag and last modified headers if config has not changed since last run
        headers = {}
        if config['etag'] and feed.config_modified is False:
            etag = feed.simple_persistence.get('%s_etag' % url_hash, None)
            if etag:
                log.debug('Sending etag %s for feed %s' % (etag, feed.name))
                headers['If-None-Match'] = etag
            modified = feed.simple_persistence.get('%s_modified' % url_hash, None)
            if modified:
                if not isinstance(modified, tuple):
                    log.debug('Invalid date was stored for last modified time.')
                else:
                    # format into an RFC 1123-compliant timestamp. We can't use
                    # time.strftime() since the %a and %b directives can be affected
                    # by the current locale, but RFC 2616 states that dates must be
                    # in English.
                    weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][modified[6]]
                    month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][modified[1] - 1]
                    headers['If-Modified-Since'] = ('%s, %02d %s %04d %02d:%02d:%02d GMT' %
                        (weekday, modified[2], month, modified[0], modified[3], modified[4], modified[5]))
                    log.debug('Sending last-modified %s for feed %s' % (headers['If-Modified-Since'], feed.name))

        # Get the feed content
        if config['url'].startswith(('http', 'https', 'ftp', 'file')):
            # Get feed using requests library
            auth = None
            if 'username' in config and 'password' in config:
                auth = (config['username'], config['password'])
            try:
                # Use the raw response so feedparser can read the headers and status values
                response = feed.requests.get(config['url'], timeout=60, headers=headers, raise_status=False,
                                             config={'decode_unicode': False}, auth=auth)
                content = response.content
            except RequestException, e:
                raise PluginError('Unable to download the RSS: %s' % e)

            # status checks
            status = response.status_code
            if status == 304:
                log.verbose('%s hasn\'t changed since last run. Not creating entries.' % config['url'])
                try:
                    # details plugin will complain if no entries are created, with this we disable that
                    details = get_plugin_by_name('details').instance
                    if feed.name not in details.no_entries_ok:
                        log.debug('adding %s to details plugin no_entries_ok' % feed.name)
                        details.no_entries_ok.append(feed.name)
                except DependencyError:
                    log.debug('unable to get details plugin')
                return []
            elif status == 401:
                raise PluginError('Authentication needed for feed %s: %s' % \
                    (feed.name, response.headers['www-authenticate']), log)
            elif status == 404:
                raise PluginError('RSS Feed %s not found' % feed.name, log)
            elif status == 500:
                raise PluginError('Internal server exception on feed %s' % feed.name, log)

            # update etag and last modified
            if config['etag']:
                etag = response.headers.get('etag')
                if etag:
                    feed.simple_persistence['%s_etag' % url_hash] = etag
                    log.debug('etag %s saved for feed %s' % (etag, feed.name))
                if  response.headers.get('last-modified'):
                    modified = feedparser._parse_date(response.headers['last-modified'])
                    feed.simple_persistence['%s_modified' % url_hash] = tuple(modified)
                    log.debug('last modified %s saved for feed %s' % (modified, feed.name))
        else:
            # This is a file, open it
            content = open(config['url'], 'rb').read()

        try:
            rss = feedparser.parse(content)
        except LookupError, e:
            raise PluginError('Unable to parse the RSS: %s' % e)

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
            elif isinstance(ex, UnicodeEncodeError):
                if rss.entries:
                    log.info('Feed has UnicodeEncodeError but seems to produce entries, ignoring the error ...')
                    ignore = True
            elif isinstance(ex, xml.sax._exceptions.SAXParseException):
                if not rss.entries:
                    # save invalid data for review, this is a bit ugly but users seem to really confused when
                    # html pages (login pages) are received
                    self.process_invalid_content(feed, content)
                    if feed.manager.options.debug:
                        log.exception(ex)
                    raise PluginError('Received invalid RSS content')
                else:
                    msg = ('Invalid XML received (%s). However feedparser still produced entries.'
                        ' Ignoring the error...' % str(ex).replace('<unknown>:', 'line '))
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
                if not rss.entries:
                    self.process_invalid_content(feed, content)
                    raise PluginError('Unhandled bozo_exception. Type: %s (feed: %s)' % \
                        (ex.__class__.__name__, feed.name), log)
                else:
                    msg = 'Invalid RSS received. However feedparser still produced entries. Ignoring the error ...'
                    if not config.get('silent', False):
                        log.info(msg)
                    else:
                        log.debug(msg)

        if 'bozo' in rss:
            if rss.bozo and not ignore:
                log.error(rss)
                log.error('Bozo exception %s on feed %s' % (type(ex), feed.name))
                return
        else:
            log.warn('feedparser bozo bit missing, feedparser bug? (FlexGet ticket #721)')

        log.debug('encoding %s' % rss.encoding)

        # new entries to be created
        entries = []

        # field name for url can be configured by setting link.
        # default value is auto but for example guid is used in some feeds
        ignored = 0
        for entry in rss.entries:

            # Check if title field is overridden in config
            title_field = config.get('title', 'title')
            # ignore entries without title
            if not entry.get(title_field):
                log.debug('skipping entry without title')
                ignored += 1
                continue

            # Set the title from the source field
            entry.title = entry[title_field]

            # convert title to ascii (cleanup)
            if config.get('ascii', False):
                entry.title = entry.title.encode('ascii', 'ignore')

            # remove annoying zero width spaces
            entry.title = entry.title.replace(u'\u200B', u'')

            # helper
            # TODO: confusing? refactor into class member ...

            def add_entry(ea):
                ea['title'] = entry.title

                # Dict with fields to grab mapping from rss field name to FlexGet field name
                fields = {'guid': 'guid',
                          'author': 'author',
                          'description': 'description',
                          'infohash': 'torrent_info_hash'}
                # extend the dict of fields to grab with other_fields list in config
                for field in config.get('other_fields', []):
                    fields[field] = field

                for rss_field, flexget_field in fields.iteritems():
                    if rss_field in entry:
                        if not isinstance(getattr(entry, rss_field), basestring):
                            # Error if this field is not a string
                            log.error('Cannot grab non text field `%s` from rss.' % rss_field)
                            # Remove field from list of fields to avoid repeated error
                            config['other_fields'].remove(rss_field)
                            continue
                        if not getattr(entry, rss_field):
                            log.debug('Not grabbing blank field %s from rss for %s.' % (rss_field, ea['title']))
                            continue
                        try:
                            ea[flexget_field] = decode_html(entry[rss_field])
                            if rss_field in config.get('other_fields', []):
                                # Print a debug message for custom added fields
                                log.debug('Field `%s` set to `%s` for `%s`' % (rss_field, ea[rss_field], ea['title']))
                        except UnicodeDecodeError:
                            log.warning('Failed to decode entry `%s` field `%s`' % (ea['title'], rss_field))
                # Also grab pubdate if available
                if hasattr(entry, 'date_parsed') and entry.date_parsed:
                    ea['rss_pubdate'] = datetime(*entry.date_parsed[:6])
                # store basic auth info
                if 'username' in config and 'password' in config:
                    ea['basic_auth_username'] = config['username']
                    ea['basic_auth_password'] = config['password']
                entries.append(ea)

            # create from enclosures if present
            enclosures = entry.get('enclosures', [])

            if len(enclosures) > 1 and not config.get('group_links'):
                # There is more than 1 enclosure, create an Entry for each of them
                log.debug('adding %i entries from enclosures' % len(enclosures))
                for enclosure in enclosures:
                    if not 'href' in enclosure:
                        log.debug('RSS-entry `%s` enclosure does not have URL' % entry.title)
                        continue
                    # There is a valid url for this enclosure, create an Entry for it
                    ee = Entry()
                    self.add_enclosure_info(ee, enclosure, config.get('filename', True), True)
                    add_entry(ee)
                # If we created entries for enclosures, we should not create an Entry for the main rss item
                continue

            # create flexget entry
            e = Entry()

            if not isinstance(config.get('link'), list):
                # If the link field is not a list, search for first valid url
                if config['link'] == 'auto':
                    # Auto mode, check for a single enclosure url first
                    if len(entry.get('enclosures', [])) == 1 and entry['enclosures'][0].get('href'):
                        self.add_enclosure_info(e, entry['enclosures'][0], config.get('filename', True))
                    else:
                        # If there is no enclosure url, check link, then guid field for urls
                        for field in ['link', 'guid']:
                            if entry.get(field):
                                e['url'] = entry[field]
                                break
                else:
                    if entry.get(config['link']):
                        e['url'] = entry[config['link']]
            else:
                # If link was passed as a list, we create a list of urls
                for field in config['link']:
                    if entry.get(field):
                        e.setdefault('url', entry[field])
                        if entry[field] not in e.setdefault('urls', []):
                            e['urls'].append(entry[field])

            if config.get('group_links'):
                # Append a list of urls from enclosures to the urls field if group_links is enabled
                e.setdefault('urls', [e['url']]).extend(
                        [enc.href for enc in entry.get('enclosures', []) if enc.get('href') not in e['urls']])

            if not e.get('url'):
                log.debug('%s does not have link (%s) or enclosure' % (entry.title, config['link']))
                ignored += 1
                continue

            add_entry(e)

        if ignored:
            if not config.get('silent'):
                log.warning('Skipped %s RSS-entries without required information (title, link or enclosures)' % ignored)

        return entries

register_plugin(InputRSS, 'rss', api_ver=2)
