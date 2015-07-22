from __future__ import unicode_literals, division, absolute_import
import logging
import re
import urllib 

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('search_freshon')


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
                'enum': ['free', 'half', 'all']
            },
        },
        'required': ['username', 'password', 'passkey'],
        'additionalProperties': False
    }
    
    @plugin.internet(log)
    def search(self, task, entry, config):
        """Freshon.tv search plugin

        Config example:
        tv_search_cpasbien:
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

        base_url = 'https://freshon.tv'
        search_fragment = 'browse.php?search=%s&tab=%s&incldead=%s'
        dl_fragment = 'download.php?type=rss&id=%s&passkey=%s'
        login_fragment = 'login.php?action=makelogin'

        if not task.requests.cookies:
            log.debug('Logging in to Freshon.tv...')
            params = {'username': config['username'],
                      'password': config['password'],
                      'login': 'Do it!'}
            urlstr = (base_url, login_fragment)
            lsrc = task.requests.post('/'.join(urlstr), data=params, verify=False)
            if str(config['username']) in lsrc.text:
                log.debug('Login to FreshonTV was successful')
            elif str('Username does not exist in the userbase') in lsrc.text:
                log.error('Invalid username or password for FreshonTV; Check your settings')
                raise plugin.PluginError("Invalid username or Password for FreshonTV.")
            else:
                log.error('Login to FreshonTV was NOT successful')
                raise plugin.PluginError("Login to FreshonTV was NOT successful")

        if config['freeleech'] == 'all':
            freeleech = 0
        elif config['freeleech'] == 'free': 
            freeleech = 3
        elif config['freeleech'] == 'half': 
            freeleech = 4

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string.replace(' ', '+'))
            query_url_fragment = urllib.quote_plus(query.encode('utf-8'))
            str_url = (base_url, search_fragment)
            url = '/'.join(str_url) % (query_url_fragment, config['category'], str(freeleech))
            log.debug('Search url: %s' % url)
            page = task.requests.get(url).content
            soup = get_soup(page)
            if soup.findAll(text=re.compile('Nothing found. Try again with a refined search string.')):
                log.debug('Search returned no results')
            else:
                max_page_number = 0
                # Check to see if there is more than 1 page of results
                pager = soup.find('div', {'class': 'pager'})
                if pager:
                    page_links = pager.find_all('a', href=True)
                else:
                    page_links = []
                if len(page_links) > 0:
                    for lnk in page_links:
                        link_text = lnk.text.strip()
                        if link_text.isdigit():
                            page_int = int(link_text)
                            if page_int > max_page_number:
                                max_page_number = page_int
                else:
                    max_page_number = 1

                # limit to 10 pages
                if max_page_number > 10:
                    max_page_number = 10

                # pages are 0 based
                nextpage = 0
                while (nextpage < max_page_number):
                    if (nextpage > 0):
                        newurl = url + '&page=' + str(nextpage)
                        log.debug('-----> NEXT PAGE : %s' % newurl)
                        f1 = task.requests.get(newurl).content
                        soup = get_soup(f1)
                    for res in soup.findAll('tr', {'class': re.compile('torrent_[0-9]*')}):
                        entry = Entry()
                        # skip if nuked
                        if res.find('img', alt='Nuked') != None:
                            continue

                        link = res.find('a', attrs={'href': re.compile('dl-torrent')})

                        entry['title'] = res.find('a', {'class': 'torrent_name_link'})['title']

                        details_url = res.find('a', {'class': 'torrent_name_link'})['href']
                        id = int((re.match('.*?([0-9]+)$', details_url).group(1)).strip())
                        str_url = (base_url, dl_fragment)
                        entry['url'] = '/'.join(str_url) % (str(id), config['passkey'])

                        log.debug('Title: %s | DL LINK: %s' % (entry['title'], entry['url']))

                        seeds = int(res.find('td', {'class': 'table_seeders'}).find('span').text.strip())
                        leechers = int(res.find('td', {'class': 'table_leechers'}).find('a').text.strip())
                        entry['torrent_seeds'] = seeds
                        entry['torrent_leeches'] = leechers
                      
                        size = res.find('td', attrs={'class': re.compile('table_size')}).text
                        size = re.search('(\d+(?:[.,]\d+)*)\s?([KMG]B)', size)

                        if size:
                            if size.group(2) == 'GB':
                                entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                            elif size.group(2) == 'MB':
                                entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                            elif size.group(2) == 'KB':
                                entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
                            else:
                                entry['content_size'] = int(float(size.group(1)) / 1024 ** 2)

                        if (int(entry['torrent_seeds']) > 0):
                            entries.add(entry)
                        else:
                            log.debug('0 SEEDS, not adding entry')
                    nextpage += 1

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFreshon, 'freshon', groups=['search'], api_ver=2)
