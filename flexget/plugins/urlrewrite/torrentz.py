from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring
from future.moves.urllib.parse import quote

import logging
import re

import feedparser
import requests

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('torrentz')

REGEXP = re.compile(r'https?://torrentz\.(eu|me|ch|in)/(?P<hash>[a-f0-9]{40})')
REPUTATIONS = {  # Maps reputation name to feed address
    'any': 'feed_any',
    'low': 'feed_low',
    'good': 'feed',
    'verified': 'feed_verified'
}


class UrlRewriteTorrentz(object):
    """Torrentz urlrewriter."""

    schema = {
        'oneOf': [
            {
                'title': 'specify options',
                'type': 'object',
                'properties': {
                    'reputation': {'enum': list(REPUTATIONS), 'default': 'good'},
                    'extra_terms': {'type': 'string'}
                },
                'additionalProperties': False
            },
            {'title': 'specify reputation', 'enum': list(REPUTATIONS), 'default': 'good'}
        ]
    }

    def process_config(self, config):
        """Return plugin configuration in advanced form"""
        if isinstance(config, basestring):
            config = {'reputation': config}
        if config.get('extra_terms'):
            config['extra_terms'] = ' ' + config['extra_terms']
        return config

    def url_rewritable(self, task, entry):
        return REGEXP.match(entry['url'])

    def url_rewrite(self, task, entry):
        thash = REGEXP.match(entry['url']).group(2)
        entry['url'] = 'https://torcache.net/torrent/%s.torrent' % thash.upper()
        entry['torrent_info_hash'] = thash

    def search(self, task, entry, config=None):
        config = self.process_config(config)
        feed = REPUTATIONS[config['reputation']]
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string + config.get('extra_terms', ''))
            for domain in ['eu', 'me', 'ch', 'in']:
                # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
                url = 'http://torrentz.%s/%s?q=%s' % (domain, feed, quote(query.encode('utf-8')))
                log.debug('requesting: %s' % url)
                try:
                    r = task.requests.get(url)
                    break
                except requests.ConnectionError as err:
                    # The different domains all resolve to the same ip, so only try more if it was a dns error
                    log.warning('torrentz.%s connection failed. Error: %s' % (domain, err))
                    continue
                except requests.RequestException as err:
                    raise plugin.PluginError('Error getting torrentz search results: %s' % err)

            else:
                raise plugin.PluginError('Error getting torrentz search results')

            if not r.content.strip():
                raise plugin.PluginError('No data from %s. Maybe torrentz is blocking the FlexGet User-Agent' % url)

            rss = feedparser.parse(r.content)

            if rss.get('bozo_exception'):
                raise plugin.PluginError('Got bozo_exception (bad rss feed)')

            for item in rss.entries:
                m = re.search(r'Size: ([\d]+) Mb Seeds: ([,\d]+) Peers: ([,\d]+) Hash: ([a-f0-9]+)',
                              item.description, re.IGNORECASE)
                if not m:
                    log.debug('regexp did not find seeds / peer data')
                    continue

                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                entry['content_size'] = int(m.group(1))
                entry['torrent_seeds'] = int(m.group(2).replace(',', ''))
                entry['torrent_leeches'] = int(m.group(3).replace(',', ''))
                entry['torrent_info_hash'] = m.group(4).upper()
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                entries.add(entry)

        log.debug('Search got %d results' % len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter', 'search'], api_ver=2)
