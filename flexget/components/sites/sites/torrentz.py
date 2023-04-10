import re
from urllib.parse import quote

import feedparser
import requests
from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='torrentz')

REGEXP = re.compile(r'https?://torrentz2\.(eu|is)/(?P<hash>[a-f0-9]{40})')
REPUTATIONS = {  # Maps reputation name to feed address
    #    'any': 'feed_any',
    #    'low': 'feed_low',
    'good': 'feed',
    #    'verified': 'feed_verified'
}


class Torrentz:
    """Torrentz search and urlrewriter"""

    schema = {
        'oneOf': [
            {
                'title': 'specify options',
                'type': 'object',
                'properties': {
                    'reputation': {'enum': list(REPUTATIONS), 'default': 'good'},
                    'extra_terms': {'type': 'string'},
                },
                'additionalProperties': False,
            },
            {'title': 'specify reputation', 'enum': list(REPUTATIONS), 'default': 'good'},
        ]
    }

    def process_config(self, config):
        """Return plugin configuration in advanced form"""
        if isinstance(config, str):
            config = {'reputation': config}
        if config.get('extra_terms'):
            config['extra_terms'] = ' ' + config['extra_terms'].strip()
        return config

    # TODO: The torrent_cache plugin is broken, so urlrewriting has been disabled for this plugin. #2307 #2363
    def url_rewritable(self, task, entry):
        return REGEXP.match(entry['url'])

    def url_rewrite(self, task, entry):
        """URL rewrite torrentz domain url with infohash to any torrent cache"""
        thash = REGEXP.match(entry['url']).group(2)
        torrent_cache = plugin.get('torrent_cache', self)
        urls = torrent_cache.infohash_urls(thash)
        # default to first shuffled url
        entry['url'] = urls[0]
        entry['urls'] = urls
        entry['torrent_info_hash'] = thash

    def search(self, task, entry, config=None):
        config = self.process_config(config)
        feed = REPUTATIONS[config['reputation']]
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string.strip() + config.get('extra_terms', ''))
            for domain in ['is', 'pl']:
                # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
                url = 'http://torrentz2.{}/{}?f={}'.format(
                    domain, feed, quote(query.encode('utf-8'))
                )
                logger.debug('requesting: {}', url)
                try:
                    r = task.requests.get(url)
                    break
                except requests.ConnectionError as err:
                    # The different domains all resolve to the same ip, so only try more if it was a dns error
                    logger.warning('torrentz.{} connection failed. Error: {}', domain, err)
                    continue
                except requests.RequestException as err:
                    raise plugin.PluginError('Error getting torrentz search results: %s' % err)

            else:
                raise plugin.PluginError('Error getting torrentz search results')

            if not r.content.strip():
                raise plugin.PluginError(
                    'No data from %s. Maybe torrentz is blocking the FlexGet User-Agent' % url
                )

            rss = feedparser.parse(r.content)

            if rss.get('bozo_exception'):
                raise plugin.PluginError('Got bozo_exception (bad rss feed)')

            for item in rss.entries:
                m = re.search(
                    r'Size: ([\d]+) Mb Seeds: ([,\d]+) Peers: ([,\d]+) Hash: ([a-f0-9]+)',
                    item.description,
                    re.IGNORECASE,
                )
                if not m:
                    logger.debug('regexp did not find seeds / peer data')
                    continue

                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                entry['content_size'] = int(m.group(1))
                entry['torrent_seeds'] = int(m.group(2).replace(',', ''))
                entry['torrent_leeches'] = int(m.group(3).replace(',', ''))
                entry['torrent_info_hash'] = m.group(4).upper()
                entry['torrent_availability'] = torrent_availability(
                    entry['torrent_seeds'], entry['torrent_leeches']
                )
                entries.add(entry)

        logger.debug('Search got {} results', len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    # TODO: The torrent_cache plugin is broken, so urlrewriting has been disabled for this plugin. #2307 #2363
    plugin.register(Torrentz, 'torrentz', interfaces=['search'], api_ver=2)
