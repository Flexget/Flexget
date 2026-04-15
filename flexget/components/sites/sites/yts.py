from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.qualities import Quality

if TYPE_CHECKING:
    from flexget.task import Task

logger = logger.bind(name='yts')

TRACKERS = [
    'udp://tracker.opentrackr.org:1337/announce',
    'udp://tracker.torrent.eu.org:451/announce',
    'udp://tracker.dler.org:6969/announce',
    'udp://open.stealth.si:80/announce',
    'https://tracker.moeblog.cn:443/announce',
    'https://tracker.zhuqiy.com:443/announce',
]


class UrlRewriteYTS:
    """YTS search."""

    schema = {'type': 'boolean'}

    @staticmethod
    def info_hash_to_magnet(info_hash: str, name: str, size: int) -> str:
        magnet = {'xt': f'urn:btih:{info_hash}', 'dn': name, 'xl': size, 'tr': TRACKERS}
        magnet_qs = urlencode(magnet, doseq=True, safe=':')
        return f'magnet:?{magnet_qs}'

    def search(self, task: Task, entry: Entry, config: bool = False):
        entries: dict[str, Entry] = {}

        if not config:
            return entries

        search_strings = (
            [entry['imdb_id']]
            if entry.get('imdb_id')
            else [normalize_unicode(s) for s in entry.get('search_strings', [entry['title']])]
        )
        for search_string in search_strings:
            url = 'https://movies-api.accel.li/api/v2/list_movies.json?query_term={}'.format(
                quote(search_string.encode('utf-8'))
            )

            logger.debug('requesting: {}', url)

            try:
                result = requests.get(url)
                try:
                    data = result.json()
                except ValueError:
                    logger.debug('Could not decode json from response: {}', result.text)
                    raise plugin.PluginError('Error getting result from yts.')
            except requests.RequestException as e:
                raise plugin.PluginError(f'Could not retrieve query from yts ({e.args[0]})')
            if not result.ok:
                raise plugin.PluginError('failed to query YTS')

            try:
                if data['data']['movie_count'] > 0:
                    for item in data['data']['movies']:
                        for torrent in item['torrents']:
                            entry = Entry()
                            entry['title'] = item['title_long']
                            entry['url'] = torrent['url']
                            entry['year'] = item['year']
                            entry['content_size'] = torrent['size_bytes']
                            entry['torrent_seeds'] = torrent['seeds']
                            entry['torrent_leeches'] = torrent['peers']
                            entry['torrent_info_hash'] = torrent['hash']
                            entry['torrent_availability'] = torrent_availability(
                                entry['torrent_seeds'], entry['torrent_leeches']
                            )
                            entry['quality'] = Quality(
                                ' '.join([
                                    torrent['quality']
                                    if torrent['quality'] != '3D'
                                    else '1080p 3D',
                                    torrent['type'],
                                    torrent.get('codec', 'h264'),
                                    f'{torrent.get("bit_depth", 8)}-bit',
                                    torrent.get('audio_codec', 'AAC')
                                    + torrent.get('audio_channels', '2.0'),
                                    'REPACK' if torrent.get('is_repack') else '',
                                ])
                            )
                            entry['magnet_uri'] = self.info_hash_to_magnet(
                                info_hash=torrent['hash'],
                                name=f'{item["title_long"]} [{entry["quality"]}] [YTS]',
                                size=torrent['size_bytes'],
                            )
                            entry['urls'] = [entry['url'], entry['magnet_uri']]
                            entry['movie_name'] = item['title']
                            entry['movie_year'] = item['year']
                            entry['imdb_id'] = item['imdb_code']
                            if entry.isvalid():
                                entries[torrent['hash']] = entry
            except Exception:
                logger.warning('Invalid return structure from YTS')

        logger.debug('Search got {} results', len(entries))
        return list(entries.values())


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteYTS, 'yts', interfaces=['search'], api_ver=2)
