from __future__ import unicode_literals, division, absolute_import
import logging
import re
import urllib 

from flexget import plugin, validator
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('search_cpasbien')

session = requests.Session()


class SearchCPASBIEN(object):
    schema = {
        'type': 'object',
        'properties':
        {
            'category': {
                'type': 'string',
                'enum': ['films', 'series', 'musique', 'films-french',
                         '720p', 'series-francaise', 'films-dvdrip', 'all',
                         'films-vostfr', '1080p', 'series-vostfr', 'ebook']
            },
        },
        'required': ['category'],
        'additionalProperties': False
    }

    @plugin.internet(log)
    def search(self, task, entry, config):
        """CPASBIEN search plugin

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

        base_url = 'http://www.cpasbien.pe'
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            search_string = search_string.replace(' ', '-').lower()
            search_string = search_string.replace('(', '')
            search_string = search_string.replace(')', '')
            query = normalize_unicode(search_string)
            query_url_fragment = urllib.quote_plus(query.encode('utf-8'))
# http://www.cpasbien.pe/recherche/ncis.html
            if config['category'] == 'all':
                str_url = (base_url, 'recherche', query_url_fragment)
                url = '/'.join(str_url)
            else:
                category_url_fragment = '%s' % config['category']
                str_url = (base_url, 'recherche', category_url_fragment, query_url_fragment)
                url = '/'.join(str_url)
            log.debug('search url: %s' % url + '.html')
# GET URL
            f = task.requests.get(url + '.html').content
            soup = get_soup(f)
            if soup.findAll(text=re.compile(' 0 torrents')):
                log.debug('search returned no results')
            else:
                nextpage = 0
                while (nextpage >= 0):
                    if (nextpage > 0):
                        newurl = url + '/page-' + str(nextpage)
                        log.debug('-----> NEXT PAGE : %s' % newurl)
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

                        log.debug('Title: %s | DL LINK: %s' % (entry['title'], entry['url']))

                        entry['torrent_seeds'] = (int(result.find('span', attrs={'class': re.compile('seed')}).text))
                        entry['torrent_leeches'] = (int(result.find('div', attrs={'class': re.compile('down')}).text))
                        sizefull = (result.find('div', attrs={'class': re.compile('poid')}).text)
                        size = sizefull[:-3]
                        unit = sizefull[-2:]
                        if unit == 'GB':
                            entry['content_size'] = int(float(size) * 1024)
                        elif unit == 'MB':
                            entry['content_size'] = int(float(size))
                        elif unit == 'KB':
                            entry['content_size'] = int(float(size) / 1024)
                        if(entry['torrent_seeds'] > 0):
                            entries.add(entry)
                        else:
                            log.debug('0 SEED, not adding entry')
                    if soup.find(text=re.compile('Suiv')):
                        nextpage += 1
                    else:
                        nextpage = -1
            return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchCPASBIEN, 'cpasbien', groups=['search'], api_ver=2)
