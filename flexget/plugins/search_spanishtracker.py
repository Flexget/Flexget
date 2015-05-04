from __future__ import unicode_literals, division, absolute_import
import urllib
import urllib2
import logging
import json
import re
import cookielib

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.utils.imdb import extract_id

from flexget.manager import Session
from flexget.db_schema import versioned_base
from requests.auth import AuthBase

from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy import Column, Unicode, Integer, DateTime

from datetime import datetime, timedelta

log = logging.getLogger('spanishtracker')
Base = versioned_base('spanishtracker', 0)

session = requests.Session()
#http://www.spanishtracker.com/download.php?id=495f45f14f384dabb4f0fa6d2293cc7899883835&f=Backstrom+-+Temporada+1+%5BHDTV%5D%5BCap.110%5D%5BEspa%C3%B1ol+Castellano%5D.torrent
URL_MATCH = re.compile('http://www.spanishtracker.com/download.php?id=.+\.torrent')

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

class JSONEncodedDict(TypeDecorator):

    """Represents an immutable structure as a json-encoded string.
    Usage:
        JSONEncodedDict(255)
    """

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

class spanishtrackerAccount(Base):
    __tablename__ = 'spanishtracker_accounts'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    username = Column(Unicode, index=True)
    auth = Column(JSONEncodedDict)
    expiry_time = Column(DateTime)

class spanishtrackerAuth(AuthBase):
    USER_AGENT = 'Mozilla/5.0'

#   RETREIVING LOGIN COOKIES ONLY ONCE A DAY
    def get_login_cookies(self, username, password):
        url_auth = 'http://www.spanishtracker.com/login.php'
        db_session = Session()
        account = db_session.query(spanishtrackerAccount).filter(
            spanishtrackerAccount.username == username).first()
        if account:
            if account.expiry_time < datetime.now():
                db_session.delete(account)
                db_session.commit()
            log.debug("Cookies found in db!")
            return account.auth
        else:
            log.debug("Getting login cookies from : %s " % url_auth)
            params = {'uid': username, 'pwd': password}
            cj = cookielib.CookieJar()
#           WE NEED A COOKIE HOOK HERE TO AVOID REDIRECT COOKIES
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
#           NEED TO BE SAME USER_AGENT THAN DOWNLOAD LINK
            opener.addheaders = [('User-agent', self.USER_AGENT)]
            login_output = None
            try:
                login_output = opener.open(url_auth, urllib.urlencode(params)).read()
            except Exception as e:
                raise UrlRewritingError("Connection Error for %s : %s" % (url_auth, e))

            authKey = None
            uid = None
            password = None

            for cookie in cj:
                if cookie.name == "authKey":
                    authKey = cookie.value
                if cookie.name == "uid":
                    uid = cookie.value
                if cookie.name == "pass":
                    password = cookie.value

            if uid is not None and \
               password is not None:
                authCookie = {'uid': uid,
                              'password': password
                              }
                db_session.add(spanishtrackerAccount(username=username,
                                                 auth=authCookie,
                                                 expiry_time=datetime.now() + timedelta(days=30)))
                db_session.commit()
                log.debug(cookie)
                return authCookie
            else:
                log.debug(login_output)
                log.error("Login failed (SpanishTracker). Check your login and password.")
                return {}
                

    def __init__(self, username, password):
        self.cookies_ = self.get_login_cookies(username,
                                               password)

    def __call__(self, r):
        headers = {'User-Agent': self.USER_AGENT,
                   'Cookie': 'uid=%s; pass=%s' % (self.cookies_['uid'], self.cookies_['password'])
                   }
        r.prepare_headers(headers)
        return r

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
    
    # UrlRewriter plugin API
    def url_rewritable(self, task, entry):
        # http://www.spanishtracker.com/download.php?id=495f45f14f384dabb4f0fa6d2293cc7899883835&f=Backstrom+-+Temporada+1+%5BHDTV%5D%5BCap.110%5D%5BEspa%C3%B1ol+Castellano%5D.torrent
        # Return true only for urls that can and should be resolved
        log.debug('Urlrewritable SpanishTracker')
        url = entry['url']
        return bool(URL_MATCH.match(url))

    # UrlRewriter plugin API
    def url_rewrite(self, task, entry):
        log.debug('Urlrewrite SpanishTracker')

    def search(self, task, entry, config=None):
        """
            Search for entries on spanishtracker
        """
        if not session.cookies:
            try:
                login_params = {'uid': config['username'],
                                'pwd': config['password']}
                session.post('http://www.spanishtracker.com/login.php', data=login_params)
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
                auth_handler = spanishtrackerAuth(config['username'],
                                        config['password'])

                entry['download_auth'] = auth_handler
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