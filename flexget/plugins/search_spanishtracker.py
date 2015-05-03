from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.utils.imdb import extract_id

log = logging.getLogger('spanishtracker')

session = requests.Session()

CATEGORIES = {
    'all': 0,

    # Movies
    'DVDRip/BluRayRip': 1,
    'Peliculas': 8,
    'DVD-R': 11,
    'Mvcd': 12,
    'Screeners': 18,
    'High Definition': 23,

    #TV
    'SeriesTV': 7
}

class SearchSpanishTracker(object):
    """spanishtracker search plugin.

    should accept:
    spanishtracker:
      username: <myuser>
      password: <mypassword>
      category: <category>

    categories:
      all
      DVDRip/BluRayRip
      Peliculas
      DVD-R
      Mvcd
      Screeners
      High Definition
      SeriesTV
    """

    schema = {
        'type': 'object',
        'properties': {
	    'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': {'type': 'string', 'enum': list(CATEGORIES)},
        },
	'required': ['username', 'password'],
        'additionalProperties': False
    }

    def search(self, task, entry, config=None):
        """
            Search for entries on spanishtracker
        """
        if not session.cookies:
            try:
                login_params = {'uid': config['username'],
                                'pwd': config['password']}
                session.post('http://www.spanishtracker.com/login.php', data=login_params, verify=False)
            except requests.RequestException as e:
                log.error('Error while logging in to SpanishTracker: %s', e)
                return
        
        categories = config.get('category', 'all')
            
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = '&category=%s' % urllib.quote(';'.join(str(c) for c in categories))
        
        base_url = 'http://www.spanishtracker.com/torrents.php?active=0'

        results = set()
        
        for search_string in entry.get('search_strings', [entry['movie_name']]):
            query = normalize_unicode(search_string)
            query_url_fragment = '&search=' + urllib.quote(query.encode('utf8'))
            # http://publichd.se/index.php?page=torrents&active=0&category=5;15&search=QUERY
            url = (base_url + category_url_fragment + query_url_fragment)
            log.debug('SpanishTracker search url: %s' % url)
            page = session.get(url).content
            soup = get_soup(page)
            links = soup.findAll('a', attrs={'href': re.compile('download\.php\?id=\d+')})
            #log.debug('SpanishTracker soup: %s' % links)
            for row in [l.find_parent('tr') for l in links]:
                dl_title = row.find('a', attrs={'href': re.compile('javascript')}).string
                dl_title = normalize_unicode(dl_title.encode('ascii', 'replace'))
                dl_href = row.find('a', attrs={'href': re.compile('download\.php\?id=\d+')}).get('href')
                idkey = re.findall('id=(.*)&f=', dl_href)
                namekey = normalize_unicode(re.findall('f=(.*)\.torrent', dl_href))
                dl_url = normalize_unicode(re.findall('id=(.*)', dl_href)[0]).encode('utf8')
                #log.debug('SpanishTracker dl url %s' % dl_url)
                td = row.findAll('td')
                entry = Entry()
                entry['url'] = 'http://www.spanishtracker.com/download.php?id=' + dl_url
                entry['title'] = dl_title
                # 4th and 3rd table cells contains amount of seeders and leeechers respectively
                entry['torrent_seeds'] = int(td[-4].string)
                entry['torrent_leeches'] = int(td[-3].string)
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                # 5th last table cell contains size, of which last two symbols are unit
                size = td[-5].text[:-2]
                unit = td[-5].text[-2:]
                if unit == 'GB':
                    entry['content_size'] = int(float(size) * 1024)
                elif unit == 'MB':
                    entry['content_size'] = int(float(size))
                elif unit == 'KB':
                    entry['content_size'] = int(float(size) / 1024)
                #log.debug('SpanishTracker entry: %s' % entry['url'])
                results.add(entry)
                
        log.debug('Finish search SpanishTracker with %d entries' % len(results))
#        if len(results) > 0:
#	    for value in results:
#	        log.debug(value['title'])
#	        log.debug(value['url'])
        return results
      

@event('plugin.register')
def register_plugin():
    plugin.register(SearchSpanishTracker, 'spanishtracker', groups=['search'], api_ver=2)