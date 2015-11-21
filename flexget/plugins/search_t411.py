from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.search import torrent_availability, normalize_unicode

from flexget.manager import Session
from flexget.db_schema import versioned_base

from requests.auth import AuthBase
from requests.compat import quote_plus

from datetime import datetime, timedelta

from sqlalchemy import Column, Unicode, Integer, DateTime

log = logging.getLogger('t411')
Base = versioned_base('t411', 0)

__author__ = 'blAStcodeM & gregaou'

T411_BASE_URL = "http://api.t411.in"

CATEGORIES = {
    'Animation': 455,
    'Animation-Serie': 637,
    'Concert': 633,
    'Documentaire': 634,
    'Emission-TV': 639,
    'Film': 631,
    'Serie-TV': 433,
    'Spectacle': 635,
    'Sport': 636,
    'Video-clips': 402
}

SUB_CATEGORIES = {
    'Anglais': [17, 540],
    'VFF': [17, 541],
    'Muet': [17, 722],
    'Multi-Francais': [17, 542],
    'Multi-Quebecois': [17, 1160],
    'VFQ': [17, 719],
    'VFSTFR': [17, 720],
    'VOASTA': 0,
    'VOSTFR': [17, 721],

    'BDrip-BRrip-SD': [7, 8],
    'BDrip-SD': [7, 8],
    'Bluray-4K': [7, 1171],
    'Bluray-Full-Remux': [7, 17],
    'BRrip-SD': [7, 8],
    'DVD-R-5': [7, 13],
    'DVD-R-9': [7, 14],
    'DVDrip': [7, 10],
    'HDlight-1080p': [7, 1208],
    'HDlight-720p': [7, 1218],
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

SUB_CATEGORIES_SERIES = {
    'Anglais': [51, 1209],
    'VFF': [51, 1210],
    'Muet': [51, 1211],
    'Multi-Francais': [51, 1212],
    'Multi-Quebecois': [51, 1213],
    'VFQ': [51, 1214],
    'VFSTFR': [51, 1215],
    'VOASTA': [51, 1217],
    'VOSTFR': [51, 1216],
}


class t411Account(Base):
    __tablename__ = 't411_account'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    username = Column(Unicode, index=True)
    token = Column(Unicode)
    expiry_time = Column(DateTime)


class t411Auth(AuthBase):

    """ Attaches HTTP Token Authentication to the given Request object."""

    def get_auth(self):
        url_auth = T411_BASE_URL + "/auth"
        log.debug("Getting token from : %s ", url_auth)
        params = {'username': self.username, 'password': self.password}
        res = requests.post(url_auth, data=params).json()
        if 'error' in res.keys():
            raise plugin.PluginError(res['error'])

        if 'token' not in res.keys():
            raise plugin.PluginError("Unable to get token ! (%s)" % res)

        return res['token']

    def update_token(self, db_session, token):
        db_session.token = token
        db_session.expiry_time = datetime.now() + timedelta(days=90)

    def get_token(self):
        db_session = Session()
        account = db_session.query(t411Account).filter(t411Account.username == self.username).first()

        if self.force_auth:
            log.debug("Token force mode !")
            token = self.get_auth()
            self.update_token(db_session, token)
        elif account:
            if account.expiry_time < datetime.now():
                log.debug("Token expired, take a new one !")
                token = self.get_auth()
                self.update_token(db_session, token)
            else:
                log.debug("Token found in db!")
                token = account.token
        else:
            token = self.get_auth()
            expiry_time = datetime.now() + timedelta(days=90)
            db_session.add(t411Account(username=self.username, token=token, expiry_time=expiry_time))
        db_session.commit()
        self.token = token
        return self.token

    def __init__(self, username, password, force_auth=False):
        self.username = username
        self.password = password
        self.force_auth = force_auth
        self.get_token()

    def __call__(self, r):
        r.headers['authorization'] = self.token
        return r


class SearchT411(object):
    """
        torrent411 Urlrewriter and search Plugin.

        ---
            -- SEARCH WITHIN SITE
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
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search torrent in private torrent tracker t411
        """

        if not isinstance(config, dict):
            config = {}

        category = config.get('category')

        if category == 'Serie-TV':
            sub_categories_dict = SUB_CATEGORIES.copy()
            sub_categories_dict.update(SUB_CATEGORIES_SERIES)

        if category in list(CATEGORIES):
            category = CATEGORIES[category]

        sub_categories = config.get('sub_category')
        if not isinstance(sub_categories, list):
            sub_categories = [sub_categories]

        filter_url = ''
        if isinstance(category, int):
            filter_url = '?cat=%s' % str(category)

            if sub_categories[0] is not None:
                sub_categories = [sub_categories_dict[c] for c in sub_categories]
                filter_url = filter_url + '&' + '&'.join([quote_plus('term[%s][]' % c[0]).
                                                          encode('utf-8') + '=' + str(c[1])
                                                          for c in sub_categories if c != 0])
        entries = set()
        auth_handler = t411Auth(config.get('username'), config.get('password'))
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            url_search = ('/torrents/search/' +
                          quote_plus(query.encode('utf-8')) +
                          filter_url)

            response = requests.get(T411_BASE_URL + url_search, auth=auth_handler)
            res_json = response.json()

            if 'errors' in res_json.keys():
                auth_handler = t411Auth(config.get('username'), config.get('password'), force_auth=True)
                res_json = requests.get(T411_BASE_URL + url_search, auth=auth_handler).json()

                if 'errors' in res_json.keys():
                    raise plugin.PluginError(res['error'])

            for torrent in res_json['torrents']:
                new_entry = Entry()
                new_entry['title'] = torrent['name']
                new_entry['url'] = T411_BASE_URL + '/torrents/download/%s' % torrent['id']
                new_entry['torrent_seeds'] = torrent['seeders']
                new_entry['torrent_leeches'] = torrent['leechers']
                new_entry['search_sort'] = torrent_availability(new_entry['torrent_seeds'],
                                                                new_entry['torrent_leeches'])
                new_entry['content_size'] = torrent['size']
                new_entry['download_auth'] = auth_handler
                entries.add(new_entry)


        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(SearchT411, 't411',
                    groups=['search'],
                    api_ver=2)
