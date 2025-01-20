import re
from math import ceil
from urllib.parse import urlparse, urlunparse

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, TimedLimiter
from flexget.utils.soup import get_soup

logger = logger.bind(name='eztv')

EZTV_MIRRORS = [
    ('https', 'eztvx.to'),
    ('https', 'eztv1.xyz'),
    ('https', 'eztv.wf'),
    ('https', 'eztv.tf'),
    ('https', 'eztv.yt'),
]


class Eztv:
    schema = {
        'type': 'boolean',
    }

    def url_rewritable(self, task, entry):
        return urlparse(entry['url']).netloc == 'eztv.ch'

    def url_rewrite(self, task, entry):
        url = entry['url']
        page = None
        for scheme, netloc in EZTV_MIRRORS:
            try:
                _, _, path, params, query, fragment = urlparse(url)
                url = urlunparse((scheme, netloc, path, params, query, fragment))
                page = task.requests.get(url).content
            except RequestException:
                logger.debug('Eztv mirror `{}` seems to be down', url)
                continue
            break

        if not page:
            raise UrlRewritingError('No mirrors found for url {}'.format(entry['url']))

        logger.debug('Eztv mirror `{}` chosen', url)
        try:
            soup = get_soup(page)
            mirrors = soup.find_all('a', attrs={'class': re.compile(r'download_\d')})
        except Exception as e:
            raise UrlRewritingError(e)

        logger.debug('{} torrent mirrors found', len(mirrors))

        if not mirrors:
            raise UrlRewritingError(f'Unable to locate download link from url {url}')

        entry['urls'] = [m.get('href') for m in mirrors]
        entry['url'] = mirrors[0].get('href')

    def api_call(self, task, entry=None, query: dict = {}) -> dict:
        try:
            return task.requests.get(
                'https://eztvx.to/api/get-torrents',
                params=query,
            ).json()
        except RequestException as e:
            if entry:
                raise plugin.PluginWarning(f'Error searching for `{entry["title"]}`: {e}')
            raise plugin.PluginWarning(f'Request error: {e}')

    def get_results(self, task, entry=None, imdb_id=None):
        query = {'limit': 100}
        if imdb_id:
            query['imdb_id'] = imdb_id
        results = self.api_call(task, entry, query)
        pages = ceil(results.get('torrents_count', query['limit']) / query['limit'])

        for page in range(min(pages, 15)):
            for result in results.get('torrents', []):
                yield Entry(
                    title=result.get('title'),
                    url=result.get('torrent_url'),
                    filename=result.get('filename'),
                    torrent_magnet=result.get('magnet_url'),
                    content_size=int(result.get('size_bytes')),
                    torrent_info_hash=result.get('hash'),
                    torrent_seeds=result.get('seeds'),
                    torrent_leeches=result.get('peers'),
                    torrent_availability=torrent_availability(
                        result.get('seeds'), result.get('peers')
                    ),
                )

            if results.get('page', page + 1) < pages:
                query['page'] = results.get('page', page + 1) + 1
                results = self.api_call(task, entry, query)

    def search(self, task, entry, config=None):
        if not config:
            return
        task.requests.add_domain_limiter(TimedLimiter('eztvx.to', '2 seconds'))
        if not entry.get('imdb_id'):
            raise plugin.PluginWarning(f'Entry `{entry["title"]}` has no `imdb_id` set')
        yield from self.get_results(task, entry, entry['imdb_id'].lstrip('tt'))

    @cached('eztv', persist='2 hours')
    def on_task_input(self, task, config=None):
        if not config:
            return
        task.requests.add_domain_limiter(TimedLimiter('eztvx.to', '2 seconds'))
        yield from self.get_results(task)


@event('plugin.register')
def register_plugin():
    plugin.register(Eztv, 'eztv', interfaces=['urlrewriter', 'search', 'input'], api_ver=2)
