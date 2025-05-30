import re
from urllib.parse import quote_plus

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='search_cpasbien')

session = requests.Session()


class SearchCPASBIEN:
    schema = {
        'type': 'object',
        'properties': {
            'category': {
                'type': 'string',
                'enum': [
                    'films',
                    'series',
                    'musique',
                    'films-french',
                    '720p',
                    'series-francaise',
                    'films-dvdrip',
                    'all',
                    'films-vostfr',
                    '1080p',
                    'series-vostfr',
                    'ebook',
                ],
            }
        },
        'required': ['category'],
        'additionalProperties': False,
    }

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """CPASBIEN search plugin.

        Config example:

        tv_search_cpasbien:
            discover:
              what:
                 - trakt_list:
                   username: xxxxxxx
                   api_key: xxxxxxx
                        series: watchlist
                  from:
                    - cpasbien:
                        category: "series-vostfr"
                  interval: 1 day
                  ignore_estimations: yes

        Category is ONE of:
            all
            films
            series
            musique
            films-french
            1080p
            720p
            series-francaise
            films-dvdrip
            films-vostfr
            series-vostfr
            ebook
        """
        base_url = 'http://www.cpasbien.io'
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            search_string = search_string.replace(' ', '-').lower()
            search_string = search_string.replace('(', '')
            search_string = search_string.replace(')', '')
            query = normalize_unicode(search_string)
            query_url_fragment = quote_plus(query.encode('utf-8'))
            # http://www.cpasbien.pe/recherche/ncis.html
            if config['category'] == 'all':
                str_url = (base_url, 'recherche', query_url_fragment)
                url = '/'.join(str_url)
            else:
                category_url_fragment = '{}'.format(config['category'])
                str_url = (base_url, 'recherche', category_url_fragment, query_url_fragment)
                url = '/'.join(str_url)
            logger.debug('search url: {}', url + '.html')
            # GET URL
            f = task.requests.get(url + '.html').content
            soup = get_soup(f)
            if soup.findAll(text=re.compile(' 0 torrents')):
                logger.debug('search returned no results')
            else:
                nextpage = 0
                while nextpage >= 0:
                    if nextpage > 0:
                        newurl = url + '/page-' + str(nextpage)
                        logger.debug('-----> NEXT PAGE : {}', newurl)
                        f1 = task.requests.get(newurl).content
                        soup = get_soup(f1)
                    for result in soup.findAll('div', attrs={'class': re.compile('ligne')}):
                        entry = Entry()
                        link = result.find('a', attrs={'href': re.compile('dl-torrent')})
                        entry['title'] = link.contents[0]
                        # REWRITE URL
                        page_link = link.get('href')
                        link_rewrite = page_link.split('/')
                        # get last value in array remove .html and replace by .torrent
                        endlink = link_rewrite[-1]
                        str_url = (base_url, '/telechargement/', endlink[:-5], '.torrent')
                        entry['url'] = ''.join(str_url)

                        logger.debug('Title: {} | DL LINK: {}', entry['title'], entry['url'])

                        entry['torrent_seeds'] = int(
                            result.find('span', attrs={'class': re.compile('seed')}).text
                        )
                        entry['torrent_leeches'] = int(
                            result.find('div', attrs={'class': re.compile('down')}).text
                        )
                        size = result.find('div', attrs={'class': re.compile('poid')}).text

                        entry['content_size'] = parse_filesize(size, si=False)

                        if entry['torrent_seeds'] > 0:
                            entries.add(entry)
                        else:
                            logger.debug('0 SEED, not adding entry')
                    if soup.find(text=re.compile('Suiv')):
                        nextpage += 1
                    else:
                        nextpage = -1
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchCPASBIEN, 'cpasbien', interfaces=['search'], api_ver=2)
