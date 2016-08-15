from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves import urllib

import logging
import json
import re
import http.cookiejar

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.tools import arithmeticEval, native_str_to_text, parse_filesize
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

from flexget.manager import Session
from flexget.db_schema import versioned_base
from requests.auth import AuthBase

from datetime import datetime, timedelta

from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy import Column, Unicode, Integer, DateTime

__author__ = 'blAStcodeM'

log = logging.getLogger('torrent411')
Base = versioned_base('torrent411', 0)

CATEGORIES = {

    'Animation': 455,
    'Animation-Serie': 637,
    'Concert': 633,
    'Documentaire': 634,
    'Emission-TV': 639,
    'Film': 631,
    'Serie-TV': 433,
    'Series': 1,
    'Spectacle': 635,
    'Sport': 636,
    'Video-clips': 402

}

SUB_CATEGORIES = {

    'Anglais': [51, 1209],
    'VFF': [51, 1210],
    'Muet': [51, 1211],
    'Multi-Francais': [51, 1212],
    'Multi-Quebecois': [51, 1213],
    'VFQ': [51, 1214],
    'VFSTFR': [51, 1215],
    'VOASTA': [51, 1217],  # new
    'VOSTFR': [51, 1216],

    # deprecated    'NTSC': [8, 20],
    # deprecated    'PAL': [8, 21],

    'BDrip-BRrip-SD': [7, 8],  # new: replaces BDrip-SD and BRrip-SD
    'BDrip-SD': [7, 8],  # deprecated: replaced by 'BDrip-BRrip-SD'
    'Bluray-4K': [7, 1171],
    'Bluray-Full-Remux': [7, 17],
    'BRrip-SD': [7, 8],  # deprecated: was 9, replaced by 'BDrip-BRrip-SD'
    'DVD-R-5': [7, 13],
    'DVD-R-9': [7, 14],
    'DVDrip': [7, 10],
    'HDlight-1080p': [7, 1208],  # new
    'HDlight-720p': [7, 1218],  # new
    'HDrip-1080p': [7, 16],
    'HDrip-720p': [7, 15],
    'TVrip-SD': [7, 11],
    'TVripHD-1080p': [7, 1162],
    'TVripHD-720p': [7, 12],
    'VCD-SVCD-VHSrip': [7, 18],
    'WEBrip': [7, 19],
    'WEBripHD-1080p': [7, 1174],
    'WEBripHD-720p': [7, 1175],
    'WEBripHD-4K': [7, 1182],

    '2D': [9, 22],
    '3D-Converti-Amateur': [9, 1045],
    '3D-Converti-Pro': [9, 24],
    '3D-Natif': [9, 23],

}

SEASONS = {
    1: [45, 968],
    2: [45, 969],
    3: [45, 970],
    4: [45, 971],
    5: [45, 972],
    6: [45, 973],
    7: [45, 974],
    8: [45, 975],
    9: [45, 976],
    10: [45, 977],
    11: [45, 978],
    12: [45, 979],
    13: [45, 980],
    14: [45, 981],
    15: [45, 982],
    16: [45, 983],
    17: [45, 984],
    18: [45, 985],
    19: [45, 986],
    20: [45, 987],
    21: [45, 988],
    22: [45, 989],
    23: [45, 990],
    24: [45, 991],
    25: [45, 994],
    26: [45, 992],
    27: [45, 993],
    28: [45, 995],
    29: [45, 996],
    30: [45, 997],
}

EPISODES = {
    1: [46, 937],
    2: [46, 938],
    3: [46, 939],
    4: [46, 940],
    5: [46, 941],
    6: [46, 942],
    7: [46, 943],
    8: [46, 944],
    9: [46, 946],
    10: [46, 947],
    11: [46, 948],
    12: [46, 949],
    13: [46, 950],
    14: [46, 951],
    15: [46, 952],
    16: [46, 954],
    17: [46, 953],
    18: [46, 955],
    19: [46, 956],
    20: [46, 957],
    21: [46, 958],
    22: [46, 959],
    23: [46, 960],
    24: [46, 961],
    25: [46, 962],
    26: [46, 963],
    27: [46, 964],
    28: [46, 965],
    29: [46, 966],
    30: [46, 967],
    31: [46, 188],
    32: [46, 189],
    33: [46, 190],
    34: [46, 191],
    35: [46, 192],
    36: [46, 193],
    37: [46, 194],
    38: [46, 195],
    39: [46, 196],
    40: [46, 197],
    41: [46, 198],
    42: [46, 199],
    43: [46, 110],
    44: [46, 111],
    45: [46, 112],
    46: [46, 113],
    47: [46, 114],
    48: [46, 115],
    49: [46, 116],
    50: [46, 117],
    51: [46, 118],
    52: [46, 119],
    53: [46, 1110],
    54: [46, 1111],
    55: [46, 1112],
    56: [46, 1113],
    57: [46, 1114],
    58: [46, 1115],
    59: [46, 1116],
    60: [46, 1117],
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


class torrent411Account(Base):
    __tablename__ = 't411_accounts'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    username = Column(Unicode, index=True)
    auth = Column(JSONEncodedDict)
    expiry_time = Column(DateTime)


class t411Auth(AuthBase):
    USER_AGENT = 'Mozilla/5.0'

    #   RETREIVING LOGIN COOKIES ONLY ONCE A DAY
    def get_login_cookies(self, username, password):
        url_auth = 'http://www.t411.ch/users/login'
        db_session = Session()
        account = db_session.query(torrent411Account).filter(
            torrent411Account.username == username).first()
        if account:
            if account.expiry_time < datetime.now():
                db_session.delete(account)
                db_session.commit()
            log.debug("Cookies found in db!")
            return account.auth
        else:
            log.debug("Getting login cookies from : %s " % url_auth)
            params = {'login': username, 'password': password, 'remember': '1'}
            cj = http.cookiejar.CookieJar()
            #           WE NEED A COOKIE HOOK HERE TO AVOID REDIRECT COOKIES
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            #           NEED TO BE SAME USER_AGENT THAN DOWNLOAD LINK
            opener.addheaders = [('User-agent', self.USER_AGENT)]
            login_output = None
            try:
                login_output = opener.open(url_auth, urllib.parse.urlencode(params)).read()
            except Exception as e:
                raise UrlRewritingError("Connection Error for %s : %s" % (url_auth, e))

            if b'confirmer le captcha' in login_output:
                log.warning("Captcha requested for login.")
                login_output = self._solveCaptcha(login_output, url_auth, params, opener)

            if b'logout' in login_output:
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

                if authKey is not None and \
                        uid is not None and \
                        password is not None:
                    authCookie = {'uid': uid,
                                  'password': password,
                                  'authKey': authKey
                                  }
                    db_session.add(torrent411Account(username=username,
                                                     auth=authCookie,
                                                     expiry_time=datetime.now() + timedelta(days=1)))
                    db_session.commit()
                    return authCookie
            else:
                log.error("Login failed (Torrent411). Check your login and password.")
                return {}

    def _solveCaptcha(self, output, url_auth, params, opener):
        """
        When trying to connect too many times with wrong password, a captcha can be requested.
        This captcha is really simple and can be solved by the provider.

        <label for="pass">204 + 65 = </label>
            <input type="text" size="40" name="captchaAnswer" id="lgn" value=""/>
            <input type="hidden" name="captchaQuery" value="204 + 65 = ">
            <input type="hidden" name="captchaToken" value="005d54a7428aaf587460207408e92145">
        <br/>

        :param output: initial login output
        :return: output after captcha resolution
        """
        html = get_soup(output)

        query = html.find('input', {'name': 'captchaQuery'})
        token = html.find('input', {'name': 'captchaToken'})
        if not query or not token:
            log.error('Unable to solve login captcha.')
            return output

        query_expr = query.attrs['value'].strip('= ')
        log.debug('Captcha query: ' + query_expr)
        answer = arithmeticEval(query_expr)

        log.debug('Captcha answer: %s' % answer)

        params['captchaAnswer'] = answer
        params['captchaQuery'] = query.attrs['value']
        params['captchaToken'] = token.attrs['value']

        return opener.open(url_auth, urllib.parse.urlencode(params)).read()

    def __init__(self, username, password):
        self.cookies_ = self.get_login_cookies(username,
                                               password)

    def __call__(self, r):
        headers = {'User-Agent': self.USER_AGENT,
                   'Cookie': 'uid=%s; pass=%s; authKey=%s' % (self.cookies_['uid'],
                                                              self.cookies_['password'],
                                                              self.cookies_['authKey'])
                   }
        r.prepare_headers(headers)
        return r


class UrlRewriteTorrent411(object):
    """
        torrent411 Urlrewriter and search Plugin.

        ---
            RSS (Two Options)

            -- RSS DOWNLOAD WITH LOGIN
            rss:
              url: http://www.t411.ch/rss/?cat=210
              username: ****
              password: ****

            - OR -

            -- RSS NORMAL URL REWRITE (i.e.: http://www.t411.ch/torrents/download/?id=12345678)
            -- WARNING: NEED CUSTOM COOKIES NOT HANDLE BY THIS PLUGIN
            rss:
              url: http://www.t411.ch/rss/?cat=210

        ---
            SEARCH WITHIN SITE
            discover:
              what:
                - emit_movie_queue: yes
              from:
                - torrent411:
                    username: xxxxxxxx  (required)
                    password: xxxxxxxx  (required)
                    category: Film
                    sub_category: Multi-Francais


            ---
              Category is one of these:

              Animation, Animation-Serie, Concert, Documentaire, Emission-TV,
              Film, Serie-TV, Series, Spectacle, Sport, Video-clips

            ---
              Sub-Category is any combination of:

              Anglais, VFF, Muet, Multi-Francais, Multi-Quebecois,
              VFQ, VFSTFR, VOSTFR, VOASTA

              BDrip-BRrip-SD, Bluray-4K, Bluray-Full-Remux, DVD-R-5,
              DVD-R-9, DVDrip, HDrip-1080p, HDrip-720p, HDlight-1080p,
              HDlight-720p, TVrip-SD, TVripHD-1080p, TVripHD-720p,
              VCD-SVCD-VHSrip, WEBrip, WEBripHD-1080p, WEBripHD-1080p

              2D, 3D-Converti-Amateur, 3D-Converti-Pro, 3D-Natif
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': {'type': 'string'},
            'sub_category': one_or_more(
                {'type': 'string', 'enum': list(SUB_CATEGORIES)}
            ),
        },
        'deprecated': '"torrent411" plugin has been replaced by the "t411" plugin.',
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    #   urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if re.match(r'^(https?://)?(www\.)?t411\.ch/torrents/(?!download/)[-A-Za-z0-9+&@#/%|?=~_|!:,.;]+', url):
            return True
        return False

    #   urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            log.error("Didn't actually get a URL...")
        else:
            url = entry['url']
            log.debug("Got the URL: %s" % entry['url'])
            rawdata = ""
            try:
                opener = urllib.request.build_opener()
                opener.addheaders = [('User-agent', 'Mozilla/5.0')]
                response = opener.open(url)
            except Exception as e:
                raise UrlRewritingError("Connection Error for %s : %s" % (url, e))
            rawdata = response.read()

            match = re.search(r"<a href=\"/torrents/download/\?id=(\d*?)\">.*\.torrent</a>", rawdata)
            if match:
                torrent_id = match.group(1)
                log.debug("Got the Torrent ID: %s" % torrent_id)
                entry['url'] = 'http://www.t411.ch/torrents/download/?id=' + torrent_id
                if 'download_auth' in entry:
                    auth_handler = t411Auth(*entry['download_auth'])
                    entry['download_auth'] = auth_handler
            else:
                raise UrlRewritingError("Cannot find torrent ID")

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from torrent411.
        """
        url_base = 'http://www.t411.ch'

        if not isinstance(config, dict):
            config = {}

        category = config.get('category')
        if category in list(CATEGORIES):
            category = CATEGORIES[category]

        sub_categories = config.get('sub_category')
        if not isinstance(sub_categories, list):
            sub_categories = [sub_categories]

        filter_url = ''
        if isinstance(category, int):
            filter_url = '&cat=%s' % str(category)

            if sub_categories[0] is not None:
                sub_categories = [SUB_CATEGORIES[c] for c in sub_categories]
                filter_url = filter_url + '&' + '&'.join([urllib.parse.quote_plus('term[%s][]' % c[0]).
                                                         encode('utf-8') + '=' + str(c[1])
                                                          for c in sub_categories])

        if 'series_season' in entry and 'series_episode' in entry:
            season = entry['series_season']
            if season in list(SEASONS):
                filter_url = filter_url + '&term[%d][]' % SEASONS[season][0] + '=' + str(SEASONS[season][1])

            episode = entry['series_episode']
            if episode in list(EPISODES):
                filter_url = filter_url + '&term[%d][]' % EPISODES[episode][0] + '=' + str(EPISODES[episode][1])

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            url_search = ('/torrents/search/?search=%40name+' +
                          urllib.parse.quote_plus(query.encode('utf-8')) +
                          filter_url)

            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            response = opener.open(url_base + url_search)

            data = response.read()
            soup = get_soup(data)
            tb = soup.find("table", class_="results")
            if not tb:
                continue

            for tr in tb.findAll('tr')[1:][:-1]:
                entry = Entry()
                nfo_link_res = re.search('torrents/nfo/\?id=(\d+)', str(tr))
                if nfo_link_res is not None:
                    tid = nfo_link_res.group(1)
                title_res = re.search(
                    '<a href=\"//www.t411.ch/torrents/([-A-Za-z0-9+&@#/%|?=~_|!:,.;]+)\" title="([^"]*)">',
                    str(tr))
                if title_res is not None:
                    entry['title'] = native_str_to_text(title_res.group(2), encoding='utf-8')
                size = tr('td')[5].contents[0]
                entry['url'] = 'http://www.t411.ch/torrents/download/?id=%s' % tid
                entry['torrent_seeds'] = tr('td')[7].contents[0]
                entry['torrent_leeches'] = tr('td')[8].contents[0]
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'],
                                                            entry['torrent_leeches'])
                size = re.search('([\.\d]+) ([GMK]?)B', size)

                entry['content_size'] = parse_filesize(size.group(0))

                auth_handler = t411Auth(config['username'],
                                        config['password'])

                entry['download_auth'] = auth_handler
                entries.add(entry)

            return sorted(entries, reverse=True,
                          key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteTorrent411, 'torrent411',
                    groups=['urlrewriter', 'search'],
                    api_ver=2
                    )
