import re
from urllib.parse import quote

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='1337x')


class Site1337x:
    """
        1337x search plugin.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'order_by': {
                        'type': 'string',
                        'enum': ['seeders', 'leechers', 'time', 'size'],
                        'default': 'seeders',
                    }
                },
                'additionalProperties': False,
            },
        ]
    }

    base_url = 'http://1337x.to/'
    errors = False

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        if url.startswith('http://1337x.to/'):
            return True
        return False

    def url_rewrite(self, task, entry):
        """
            Gets the download information for 1337x result
        """

        url = entry['url']

        logger.info('1337x rewriting download url: {}', url)

        try:
            page = task.requests.get(url)
            logger.debug('requesting: {}', page.url)
        except RequestException as e:
            logger.error('1337x request failed: {}', e)
            raise UrlRewritingError('1337x request failed: %s' % e)

        soup = get_soup(page.content)

        magnet_url = str(soup.find('a', href=re.compile(r'^magnet:\?')).get('href')).lower()
        torrent_url = str(soup.find('a', href=re.compile(r'\.torrent$')).get('href')).lower()

        entry['url'] = torrent_url
        entry.setdefault('urls', []).append(torrent_url)
        entry['urls'].append(magnet_url)

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
            Search for entries on 1337x
        """

        if not isinstance(config, dict):
            config = {}

        order_by = ''
        sort_order = ''
        if isinstance(config.get('order_by'), str):
            if config['order_by'] != 'leechers':
                order_by = '/{0}/desc'.format(config['order_by'])
                sort_order = 'sort-'

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            query = '{0}search/{1}{2}/1/'.format(
                sort_order, quote(search_string.encode('utf8')), order_by
            )
            logger.debug(
                'Using search params: {}; ordering by: {}', search_string, order_by or 'default'
            )
            try:
                page = task.requests.get(self.base_url + query)
                logger.debug('requesting: {}', page.url)
            except RequestException as e:
                logger.error('1337x request failed: {}', e)
                continue

            soup = get_soup(page.content)
            if soup.find('div', attrs={'class': 'table-list-wrap'}) is not None:
                for link in soup.find('div', attrs={'class': 'table-list-wrap'}).findAll(
                    'a', href=re.compile('^/torrent/')
                ):
                    li = link.parent.parent

                    title = str(link.text).replace('...', '')
                    info_url = self.base_url + str(link.get('href'))[1:]
                    seeds = int(li.find('td', class_='seeds').string)
                    leeches = int(li.find('td', class_='leeches').string)
                    size = str(li.find('td', class_='coll-4').contents[0])

                    size = parse_filesize(size)

                    e = Entry()

                    e['url'] = info_url
                    e['title'] = title
                    e['torrent_seeds'] = seeds
                    e['torrent_leeches'] = leeches
                    e['torrent_availability'] = torrent_availability(
                        e['torrent_seeds'], e['torrent_leeches']
                    )
                    e['content_size'] = size

                    entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Site1337x, '1337x', interfaces=['urlrewriter', 'search'], api_ver=2)
