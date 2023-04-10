from urllib.parse import quote

import feedparser
from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='nyaa')

CATEGORIES = {
    'all': '0_0',
    # Anime
    'anime': '1_0',
    'anime amv': '1_1',
    'anime eng': '1_2',
    'anime non-eng': '1_3',
    'anime raw': '1_4',
    # Audio
    'audio': '2_0',
    'audio lless': '2_1',
    'audio lossy': '2_2',
    # Literature
    'lit': '3_0',
    'lit eng': '3_1',
    'lit non-eng': '3_2',
    'lit raw': '3_3',
    # Live Action
    'liveact': '4_0',
    'liveact eng': '4_1',
    'liveact idol': '4_2',
    'liveact non-eng': '4_3',
    'liveact raw': '4_4',
    # Pictures
    'pics': '5_0',
    'pics graphics': '5_1',
    'pics photos': '5_2',
    # Software
    'software': '6_0',
    'software apps': '6_1',
    'software games': '6_2',
}
FILTERS = ['all', 'filter remakes', 'trusted only']


class UrlRewriteNyaa:
    """Nyaa urlrewriter and search plugin."""

    schema = {
        'oneOf': [
            {'type': 'string', 'enum': list(CATEGORIES)},
            {
                'type': 'object',
                'properties': {
                    'category': {'type': 'string', 'enum': list(CATEGORIES)},
                    'filter': {'type': 'string', 'enum': list(FILTERS)},
                },
                'additionalProperties': False,
            },
        ]
    }

    def search(self, task, entry, config):
        if not isinstance(config, dict):
            config = {'category': config}
        config.setdefault('category', 'anime eng')
        config.setdefault('filter', 'all')
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            name = normalize_unicode(search_string)
            url = 'https://www.nyaa.si/?page=rss&q={}&c={}&f={}'.format(
                quote(name.encode('utf-8')),
                CATEGORIES[config['category']],
                FILTERS.index(config['filter']),
            )

            logger.debug('requesting: {}', url)
            rss = feedparser.parse(url)

            status = rss.get('status', False)
            if status != 200:
                logger.debug('Search result not 200 (OK), received {}', status)
            if status >= 400:
                continue

            ex = rss.get('bozo_exception', False)
            if ex:
                logger.error('Got bozo_exception (bad feed) on {}', url)
                continue

            for item in rss.entries:
                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                entry['torrent_seeds'] = int(item.nyaa_seeders)
                entry['torrent_leeches'] = int(item.nyaa_leechers)
                entry['torrent_info_hash'] = item.nyaa_infohash
                entry['torrent_availability'] = torrent_availability(
                    entry['torrent_seeds'], entry['torrent_leeches']
                )
                if item.nyaa_size:
                    entry['content_size'] = parse_filesize(item.nyaa_size)

                entries.add(entry)

        return entries

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('https://www.nyaa.si/view/')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('view', 'download') + ".torrent"


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNyaa, 'nyaa', interfaces=['search', 'urlrewriter'], api_ver=2)
