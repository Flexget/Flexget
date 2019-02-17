from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import tobytes
from future.moves.urllib.parse import urlparse, urlsplit

import hashlib
import os
import logging
import xml.sax
import posixpath
import http.client
from datetime import datetime

import dateutil.parser

import feedparser
from requests import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.tools import decode_html
from flexget.utils.pathscrub import pathscrub

log = logging.getLogger('rss')
feedparser.registerDateHandler(lambda date_string: dateutil.parser.parse(date_string).timetuple())


def fp_field_name(name):
    """Translates literal field name to the sanitized one feedparser will use."""
    return name.replace(':', '_').lower()


class InputRSS(object):
    """
    Parses RSS feed.

    Hazzlefree configuration for public rss feeds::

      rss: <url>

    Configuration with basic http authentication::

      rss:
        url: <url>
        username: <name>
        password: <password>

    Advanced usages:

    You may wish to clean up the entry by stripping out all non-ascii characters.
    This can be done by setting ascii value to yes.

    Example::

      rss:
        url: <url>
        ascii: yes

    In case RSS-feed uses some nonstandard field for urls and automatic detection fails
    you can configure plugin to use url from any feedparser entry attribute.

    Example::

      rss:
        url: <url>
        link: guid

    If you want to keep information in another rss field attached to the flexget entry,
    you can use the other_fields option.

    Example::

      rss:
        url: <url>
        other_fields: [date]

    You can disable few possibly annoying warnings by setting silent value to
    yes on feeds where there are frequently invalid items.

    Example::

      rss:
        url: <url>
        silent: yes

    You can group all the links of an item, to make the download plugin tolerant
    to broken urls: it will try to download each url until one works.
    Links are enclosures plus item fields given by the link value, in that order.
    The value to set is "group_links".

    Example::

      rss:
        url: <url>
        group_links: yes
    """

    schema = {
        'type': ['string', 'object'],
        # Simple form, just url or file
        'anyOf': [{'format': 'url'}, {'format': 'file'}],
        # Advanced form, with options
        'properties': {
            'url': {'type': 'string', 'anyOf': [{'format': 'url'}, {'format': 'file'}]},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'title': {'type': 'string'},
            'link': one_or_more({'type': 'string'}),
            'silent': {'type': 'boolean', 'default': False},
            'ascii': {'type': 'boolean', 'default': False},
            'escape': {'type': 'boolean', 'default': False},
            'filename': {'type': 'boolean'},
            'group_links': {'type': 'boolean', 'default': False},
            'all_entries': {'type': 'boolean', 'default': True},
            'other_fields': {
                'type': 'array',
                'items': {
                    # Items can be a string, or a dict with a string value
                    'type': ['string', 'object'],
                    'additionalProperties': {'type': 'string'},
                },
            },
        },
        'required': ['url'],
        'additionalProperties': False,
    }

    def build_config(self, config):
        """Set default values to config"""
        if isinstance(config, str):
            config = {'url': config}
        else:
            # Make a copy so that original config is not modified
            config = dict(config)
        # set the default link value to 'auto'
        config.setdefault('link', 'auto')
        # Convert any field names from the config to format feedparser will use for 'link', 'title' and 'other_fields'
        if config['link'] != 'auto':
            if not isinstance(config['link'], list):
                config['link'] = [config['link']]
            config['link'] = list(map(fp_field_name, config['link']))
        config.setdefault('title', 'title')
        config['title'] = fp_field_name(config['title'])
        if config.get('other_fields'):
            other_fields = []
            for item in config['other_fields']:
                if isinstance(item, str):
                    key, val = item, item
                else:
                    key, val = list(item.items())[0]
                other_fields.append({fp_field_name(key): val.lower()})
            config['other_fields'] = other_fields
        # set default value for group_links as deactivated
        config.setdefault('group_links', False)
        # set default for all_entries
        config.setdefault('all_entries', True)
        return config

    def process_invalid_content(self, task, data, url):
        """If feedparser reports error, save the received data and log error."""

        if data is None:
            log.critical('Received empty page - no content')
            return
        else:
            data = tobytes(data)

        ext = 'xml'
        if b'<html>' in data.lower():
            log.critical('Received content is HTML page, not an RSS feed')
            ext = 'html'
        if b'login' in data.lower() or b'username' in data.lower():
            log.critical('Received content looks a bit like login page')
        if b'error' in data.lower():
            log.critical('Received content looks a bit like error page')
        received = os.path.join(task.manager.config_base, 'received')
        if not os.path.isdir(received):
            os.mkdir(received)
        filename = task.name
        sourcename = urlparse(url).netloc
        if sourcename:
            filename += '-' + sourcename
        filename = pathscrub(filename, filename=True)
        filepath = os.path.join(received, '%s.%s' % (filename, ext))
        with open(filepath, 'wb') as f:
            f.write(data)
        log.critical('I have saved the invalid content to %s for you to view', filepath)

    def escape_content(self, content):
        valid_escapes = (b'&quot;', b'&apos;', b'&lt;', b'&gt;', b'&amp;')
        future_result = []
        in_cdata_block = False

        for idx, char in enumerate(bytes(content)):

            char = bytes([char])
            if not in_cdata_block and char == b'&':
                if not content[idx : idx + 7].startswith(valid_escapes):
                    char = b'&amp;'
            elif not in_cdata_block and char == b'<' and content[idx : idx + 9] == b'<![CDATA[':
                in_cdata_block = True
            elif in_cdata_block and char == b']' and content[idx - 1 : idx + 2] == b']]>':
                in_cdata_block = False
            future_result.append(char)
        return b''.join(future_result)

    def add_enclosure_info(self, entry, enclosure, filename=True, multiple=False):
        """Stores information from an rss enclosure into an Entry."""
        entry['url'] = enclosure['href']
        # get optional meta-data
        if 'length' in enclosure:
            try:
                entry['size'] = int(enclosure['length'])
            except ValueError:
                entry['size'] = 0
        if 'type' in enclosure:
            entry['type'] = enclosure['type']
        # TODO: better and perhaps join/in download plugin?
        # Parse filename from enclosure url
        basename = posixpath.basename(urlsplit(entry['url']).path)
        # If enclosure has size OR there are multiple enclosures use filename from url
        if (entry.get('size') or multiple and basename) and filename:
            entry['filename'] = basename
            log.trace('filename `%s` from enclosure', entry['filename'])

    @cached('rss')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        config = self.build_config(config)

        log.debug('Requesting task `%s` url `%s`', task.name, config['url'])

        # Used to identify which etag/modified to use
        url_hash = hashlib.md5(config['url'].encode('utf-8')).hexdigest()

        # set etag and last modified headers if config has not changed since
        # last run and if caching wasn't disabled with --no-cache argument.
        all_entries = (
            config['all_entries']
            or task.config_modified
            or task.options.nocache
            or task.options.retry
        )
        headers = task.requests.headers
        if not all_entries:
            etag = task.simple_persistence.get('%s_etag' % url_hash, None)
            if etag:
                log.debug('Sending etag %s for task %s', etag, task.name)
                headers['If-None-Match'] = etag
            modified = task.simple_persistence.get('%s_modified' % url_hash, None)
            if modified:
                if not isinstance(modified, str):
                    log.debug('Invalid date was stored for last modified time.')
                else:
                    headers['If-Modified-Since'] = modified
                    log.debug(
                        'Sending last-modified %s for task %s',
                        headers['If-Modified-Since'],
                        task.name,
                    )

        # Get the feed content
        if config['url'].startswith(('http', 'https', 'ftp', 'file')):
            # Get feed using requests library
            auth = None
            if 'username' in config and 'password' in config:
                auth = (config['username'], config['password'])
            try:
                # Use the raw response so feedparser can read the headers and status values
                response = task.requests.get(
                    config['url'], timeout=60, headers=headers, raise_status=False, auth=auth
                )
                content = response.content
            except RequestException as e:
                raise plugin.PluginError(
                    'Unable to download the RSS for task %s (%s): %s'
                    % (task.name, config['url'], e)
                )
            if config.get('ascii'):
                # convert content to ascii (cleanup), can also help with parsing problems on malformed feeds
                content = response.text.encode('ascii', 'ignore')

            # status checks
            status = response.status_code
            if status == 304:
                log.verbose(
                    '%s hasn\'t changed since last run. Not creating entries.', config['url']
                )
                # Let details plugin know that it is ok if this feed doesn't produce any entries
                task.no_entries_ok = True
                return []
            elif status == 401:
                raise plugin.PluginError(
                    'Authentication needed for task %s (%s): %s'
                    % (task.name, config['url'], response.headers['www-authenticate']),
                    log,
                )
            elif status == 404:
                raise plugin.PluginError(
                    'RSS Feed %s (%s) not found' % (task.name, config['url']), log
                )
            elif status == 500:
                raise plugin.PluginError(
                    'Internal server exception on task %s (%s)' % (task.name, config['url']), log
                )
            elif status != 200:
                raise plugin.PluginError(
                    'HTTP error %s received from %s' % (status, config['url']), log
                )

            # update etag and last modified
            if not config['all_entries']:
                etag = response.headers.get('etag')
                if etag:
                    task.simple_persistence['%s_etag' % url_hash] = etag
                    log.debug('etag %s saved for task %s', etag, task.name)
                if response.headers.get('last-modified'):
                    modified = response.headers['last-modified']
                    task.simple_persistence['%s_modified' % url_hash] = modified
                    log.debug('last modified %s saved for task %s', modified, task.name)
        else:
            # This is a file, open it
            with open(config['url'], 'rb') as f:
                content = f.read()
            if config.get('ascii'):
                # Just assuming utf-8 file in this case
                content = content.decode('utf-8', 'ignore').encode('ascii', 'ignore')

        if not content:
            log.error('No data recieved for rss feed.')
            return []
        if config.get('escape'):
            log.debug("Trying to escape unescaped in RSS")
            content = self.escape_content(content)
        try:
            rss = feedparser.parse(content)
        except LookupError as e:
            raise plugin.PluginError('Unable to parse the RSS (from %s): %s' % (config['url'], e))

        # check for bozo
        ex = rss.get('bozo_exception', False)
        if ex or rss.get('bozo'):
            if rss.entries:
                msg = (
                    'Bozo error %s while parsing feed, but entries were produced, ignoring the error.'
                    % type(ex)
                )
                if config.get('silent', False):
                    log.debug(msg)
                else:
                    log.verbose(msg)
            else:
                if isinstance(ex, feedparser.NonXMLContentType):
                    # see: http://www.feedparser.org/docs/character-encoding.html#advanced.encoding.nonxml
                    log.debug('ignoring feedparser.NonXMLContentType')
                elif isinstance(ex, feedparser.CharacterEncodingOverride):
                    # see: ticket 88
                    log.debug('ignoring feedparser.CharacterEncodingOverride')
                elif isinstance(ex, UnicodeEncodeError):
                    raise plugin.PluginError('Feed has UnicodeEncodeError while parsing...')
                elif isinstance(
                    ex, (xml.sax._exceptions.SAXParseException, xml.sax._exceptions.SAXException)
                ):
                    # save invalid data for review, this is a bit ugly but users seem to really confused when
                    # html pages (login pages) are received
                    self.process_invalid_content(task, content, config['url'])
                    if task.options.debug:
                        log.error('bozo error parsing rss: %s' % ex)
                    raise plugin.PluginError(
                        'Received invalid RSS content from task %s (%s)'
                        % (task.name, config['url'])
                    )
                elif isinstance(ex, http.client.BadStatusLine) or isinstance(ex, IOError):
                    raise ex  # let the @internet decorator handle
                else:
                    # all other bozo errors
                    self.process_invalid_content(task, content, config['url'])
                    raise plugin.PluginError(
                        'Unhandled bozo_exception. Type: %s (task: %s)'
                        % (ex.__class__.__name__, task.name),
                        log,
                    )

        log.debug('encoding %s', rss.encoding)

        last_entry_id = ''
        if not all_entries:
            # Test to make sure entries are in descending order
            if (
                rss.entries
                and rss.entries[0].get('published_parsed')
                and rss.entries[-1].get('published_parsed')
            ):
                if rss.entries[0]['published_parsed'] < rss.entries[-1]['published_parsed']:
                    # Sort them if they are not
                    rss.entries.sort(key=lambda x: x['published_parsed'], reverse=True)
            last_entry_id = task.simple_persistence.get('%s_last_entry' % url_hash)

        # new entries to be created
        entries = []

        # Dict with fields to grab mapping from rss field name to FlexGet field name
        fields = {
            'guid': 'guid',
            'author': 'author',
            'description': 'description',
            'infohash': 'torrent_info_hash',
        }
        # extend the dict of fields to grab with other_fields list in config
        for field_map in config.get('other_fields', []):
            fields.update(field_map)

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

            # Check we haven't already processed this entry in a previous run
            if last_entry_id == entry.title + entry.get('guid', ''):
                log.verbose('Not processing entries from last run.')
                # Let details plugin know that it is ok if this task doesn't produce any entries
                task.no_entries_ok = True
                break

            # remove annoying zero width spaces
            entry.title = entry.title.replace(u'\u200B', u'')

            # helper
            # TODO: confusing? refactor into class member ...

            def add_entry(ea):
                ea['title'] = entry.title

                # fields dict may be modified during this loop, so loop over a copy (fields.items())
                for rss_field, flexget_field in list(fields.items()):
                    if rss_field in entry:
                        if rss_field == 'content':
                            content_str = ''
                            for content in entry[rss_field]:
                                try:
                                    content_str += decode_html(content.value)
                                except UnicodeDecodeError:
                                    log.warning(
                                        'Failed to decode entry `%s` field `%s`',
                                        ea['title'],
                                        rss_field,
                                    )
                            ea[flexget_field] = content_str
                            log.debug(
                                'Field `%s` set to `%s` for `%s`',
                                rss_field,
                                ea[rss_field],
                                ea['title'],
                            )
                            continue
                        if not isinstance(getattr(entry, rss_field), str):
                            # Error if this field is not a string
                            log.error('Cannot grab non text field `%s` from rss.', rss_field)
                            # Remove field from list of fields to avoid repeated error
                            del fields[rss_field]
                            continue
                        if not getattr(entry, rss_field):
                            log.debug(
                                'Not grabbing blank field %s from rss for %s.',
                                rss_field,
                                ea['title'],
                            )
                            continue
                        try:
                            ea[flexget_field] = decode_html(entry[rss_field])
                            if rss_field in config.get('other_fields', []):
                                # Print a debug message for custom added fields
                                log.debug(
                                    'Field `%s` set to `%s` for `%s`',
                                    rss_field,
                                    ea[rss_field],
                                    ea['title'],
                                )
                        except UnicodeDecodeError:
                            log.warning(
                                'Failed to decode entry `%s` field `%s`', ea['title'], rss_field
                            )
                # Also grab pubdate if available
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    ea['rss_pubdate'] = datetime(*entry.published_parsed[:6])
                # store basic auth info
                if 'username' in config and 'password' in config:
                    ea['download_auth'] = (config['username'], config['password'])
                entries.append(ea)

            # create from enclosures if present
            enclosures = entry.get('enclosures', [])

            if len(enclosures) > 1 and not config.get('group_links'):
                # There is more than 1 enclosure, create an Entry for each of them
                log.debug('adding %i entries from enclosures', len(enclosures))
                for enclosure in enclosures:
                    if 'href' not in enclosure:
                        log.debug('RSS-entry `%s` enclosure does not have URL', entry.title)
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
                    if len(entry.get('enclosures', [])) == 1 and entry['enclosures'][0].get(
                        'href'
                    ):
                        self.add_enclosure_info(
                            e, entry['enclosures'][0], config.get('filename', True)
                        )
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
                    [
                        enc.href
                        for enc in entry.get('enclosures', [])
                        if enc.get('href') not in e['urls']
                    ]
                )

            if not e.get('url'):
                log.debug('%s does not have link (%s) or enclosure', entry.title, config['link'])
                ignored += 1
                continue

            add_entry(e)

        # Save last spot in rss
        if rss.entries:
            log.debug('Saving location in rss feed.')

            try:
                entry_id = rss.entries[0].title + rss.entries[0].get('guid', '')
            except AttributeError:
                entry_id = ''

            if entry_id.strip():
                task.simple_persistence['%s_last_entry' % url_hash] = entry_id
            else:
                log.debug('rss feed location saving skipped: no title information in first entry')

        if ignored:
            if not config.get('silent'):
                log.warning(
                    'Skipped %s RSS-entries without required information (title, link or enclosures)',
                    ignored,
                )

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputRSS, 'rss', api_ver=2)
