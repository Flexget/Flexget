from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlsplit, parse_qs

import logging
import re
import urllib

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize
from flexget.utils.search import normalize_scene

log = logging.getLogger('search_freshon')

BASE_URL = 'https://freshon.tv'
SEARCH_PAGE = 'browse.php'
DL_PAGE = 'download.php'
LOGIN_PAGE = 'login.php'
LEECHSTATUS = {
    'all': 0,
    'free': 3,
    'half': 4
}


class SearchFreshon(object):

    schema = {
        'type': 'object',
        'properties':
        {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'passkey': {'type': 'string'},
            'category': {
                'type': 'string',
                'default': 'all',
                'enum': ['hd', 'webdl', 'all']
            },
            'freeleech': {
                'type': 'string',
                'default': 'all',
                'enum': list(LEECHSTATUS.keys())
            },
            'page_limit': {'type': 'integer', 'default': 10},
        },
        'required': ['username', 'password', 'passkey'],
        'additionalProperties': False
    }

    @plugin.internet(log)
    def search(self, task, entry, config):
        """Freshon.tv search plugin

        Config example:
        tv_search_freshon:
            discover:
              what:
                 - trakt_list:
                     username: xxxxxxx
                     password: xxxxxxx
                     list: somelist
                     type: shows
                  from:
                    - freshon:
                        username: xxxxxx
                        password: xxxxxx
                        passkey: xxxxx
                  interval: 1 day
                  ignore_estimations: yes

        Category is one of:
            all
            hd
            webdl

        Freeleech is one of:
            all
            free
            half
        """
        self.config = config

        if not task.requests.cookies:
            self.login(task)

        freeleech = LEECHSTATUS[config['freeleech']]

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_scene(search_string)
            params = {
                'search': query,
                'tab': config['category'],
                'incldead': freeleech,
                'page': None
            }
            url = "%s/%s" % (BASE_URL, SEARCH_PAGE)
            log.debug('Search : %s %s', url, params)
            try:
                page = task.requests.get(url, params=params).content
            except RequestsException:
                log.error('Could not get page %s, %s, skipping',  url, params)
                continue
            soup = get_soup(page)
            if soup.findAll(text=re.compile('Nothing found. Try again with '
                                            'a refined search string.')):
                log.debug('Search returned no results')
            else:
                page_number = self.get_page_number(soup)

                # pages are 0 based
                nextpage = 0
                while (nextpage < page_number):
                    if (nextpage > 0):
                        params['page'] = nextpage
                        log.debug('-----> NEXT PAGE : %s %s', url, params)
                        try:
                            f1 = task.requests.get(url, params=params).content
                        except RequestsException:
                            log.error('Could not get page %s, %s, skipping',
                                      url, params)
                            continue
                        soup = get_soup(f1)
                    results = soup.findAll('tr', {
                        'class': re.compile('torrent_[0-9]*')
                    })
                    for res in results:
                        entry = self.parse_entry(res)
                        if entry:
                            entries.add(entry)

                    nextpage += 1

        return entries

    def login(self, task):
        log.debug('Logging in to Freshon.tv...')
        params = {'action': 'makelogin'}
        data = {
            'username': self.config['username'],
            'password': self.config['password'],
            'login': 'Do it!'
        }
        url = "%s/%s" % (BASE_URL, LOGIN_PAGE)
        lsrc = task.requests.post(url, params=params, data=data)
        if self.config['username'] in lsrc.text:
            log.debug('Login to FreshonTV was successful')
        elif 'Username does not exist in the userbase' in lsrc.text:
            log.error('Invalid credentials FreshonTV')
            raise plugin.PluginError("Invalid credentials for FreshonTV.")
        else:
            log.error('Login to FreshonTV was NOT successful')
            raise plugin.PluginError("Login to FreshonTV was NOT successful")

    def get_page_number(self, html_soup):
        page_number = 0
        # Check to see if there is more than 1 page of results
        pager = html_soup.find('div', {'class': 'pager'})
        if pager:
            page_links = pager.find_all('a', href=True)
        else:
            page_links = []
        if len(page_links) > 0:
            for lnk in page_links:
                link_text = lnk.text.strip()
                if link_text.isdigit():
                    page_int = int(link_text)
                    if page_int > page_number:
                        page_number = page_int
        else:
            page_number = 1

        return min(page_number, self.config['page_limit'])

    def parse_entry(self, res):
        entry = Entry()

        entry['title'] = res.find('a', {'class': 'torrent_name_link'})['title']
        # skip if nuked
        if res.find('img', alt='Nuked'):
            log.info('Skipping entry %s (nuked)', entry['title'])
            return None

        details_url = res.find('a', {'class': 'torrent_name_link'})['href']
        torrent_id = parse_qs(urlsplit(details_url).query)['id'][0]
        params = {
            'type': 'rss',
            'id': torrent_id,
            'passkey': self.config['passkey']
        }
        url = '%s/%s?%s' % (BASE_URL, DL_PAGE, urllib.urlencode(params))
        entry['url'] = url

        log.debug('Title: %s | DL LINK: %s', (entry['title'], entry['url']))

        seeds = res.find('td', {'class': 'table_seeders'}) \
            .find('span').text.strip()
        leechers = res.find('td', {'class': 'table_leechers'}) \
            .find('a').text.strip()
        entry['torrent_seeds'] = int(seeds)
        entry['torrent_leeches'] = int(leechers)

        size = res.find('td', attrs={'class': re.compile('table_size')}).text
        entry['content_size'] = parse_filesize(size)

        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFreshon, 'freshon', interfaces=['search'], api_ver=2)
