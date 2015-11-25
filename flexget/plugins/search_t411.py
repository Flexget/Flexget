"""Search plugin for torrent411 french tracker."""
from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import torrent_availability, normalize_unicode

from flexget.manager import Session
from flexget.db_schema import versioned_base

from requests.auth import AuthBase
from requests.compat import quote_plus

from datetime import datetime, timedelta

from sqlalchemy import Column, Unicode, DateTime

log = logging.getLogger('t411')
Base = versioned_base('t411', 0)

__author__ = 'blAStcodeM & gregaou'

BASE_URL = "http://api.t411.in"

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


class T411Account(Base):

    """T411Account, database class."""

    __tablename__ = 't411_account'

    username = Column(Unicode, primary_key=True)
    token = Column(Unicode)
    expiry_time = Column(DateTime)

    def __init__(self, username, token, expiry_time):
        """__init__.

        :param username: string User login
        :param token: string User token
        :param expiry_time: date User token expire date
        """
        super(T411Account, self).__init__()
        self.username = username
        self.token = token
        self.expiry_time = expiry_time


class T411Auth(AuthBase):

    """Attaches HTTP Token Authentication to the given Request object."""

    def get_auth(self):
        """get_auth.

        :returns: token string
        """
        url_auth = BASE_URL + "/auth"
        log.debug("Getting token from : %s ", url_auth)
        params = {'username': self.username, 'password': self.password}

        try:
            res = self.requests.post(url_auth, data=params).json()
        except self.requests.exceptions.RequestException as exc:
            raise plugin.PluginError(exc)

        if 'error' in res.keys():
            raise plugin.PluginError(res['error'])

        if 'token' not in res.keys():
            raise plugin.PluginError("Unable to get token ! (%s)" % res)

        return res['token']

    @classmethod
    def update_token(cls, db_session, token):
        """update_token.

        Update token and expiration time in database.

        :param db_session: Database session
        :param token: token string
        """
        db_session.token = token
        db_session.expiry_time = datetime.now() + timedelta(days=90)

    def get_token(self):
        """get_token.

        Set token string from database, or get a new one if necessary.

        :returns: token string
        """
        if self.token is not None and not self.force_auth:
            log.debug("Token already return one time, returning the same !")
            return self.token

        with Session() as db_session:
            account = db_session.query(T411Account).filter(
                T411Account.username == self.username).first()

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
                db_session.add(T411Account(self.username, token, expiry_time))
            self.token = token
            return self.token

    def __init__(self, task_requests, username, password, force_auth=False):
        """__init__.

        :param task_requests: requests objects given to the task
        :param username: user login
        :param password: user password
        :param force_auth: boolean to force or not new token and authorization
        """
        self.requests = task_requests
        self.username = username
        self.password = password
        self.token = None
        self.force_auth = force_auth
        self.get_token()

    def __call__(self, r):
        """__call__.

        Set requests headers for each call.

        :param r: requests object
        """
        r.headers['authorization'] = self.token
        return r


class SearchT411(object):

    """torrent411 Urlrewriter and search Plugin.

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

    @classmethod
    def get_entry(cls, json, auth_handler):
        """get_entry.

        :param json: json coming from t411 search request
        :param auth_handler: request AuthBase object
        :returns: Entry object created from json object
        """
        log.verbose(json)
        entry = Entry()
        entry['title'] = json['name']
        entry['url'] = (BASE_URL + '/torrents/download/%s' % json['id'])
        entry['torrent_seeds'] = json['seeders']
        entry['torrent_leeches'] = json['leechers']
        entry['search_sort'] = torrent_availability(entry['torrent_seeds'],
                                                    entry['torrent_leeches'])
        entry['content_size'] = json['size']
        entry['download_auth'] = auth_handler
        return entry

    @classmethod
    def get_filter_url(cls, category, sub_categories):
        """get_filter_url.

        Return filter url for search with filters

        :param category: string category set in params
        :param sub_categories: array subcategores set in params
        :returns: string url to call with filters
        """
        if category == 'Serie-TV':
            sub_categories_dict = SUB_CATEGORIES.copy()
            sub_categories_dict.update(SUB_CATEGORIES_SERIES)

        if category in list(CATEGORIES):
            category = CATEGORIES[category]

        if not isinstance(sub_categories, list):
            sub_categories = [sub_categories]

        filter_url = ''
        if isinstance(category, int):
            filter_url = '?cat=%s' % str(category)

            if sub_categories[0] is not None:
                sub_categories = [sub_categories_dict[c]
                                  for c in sub_categories]
                filter_url = (filter_url + '&' +
                              '&'.join([quote_plus('term[%s][]' % c[0]).
                                        encode('utf-8') + '=' + str(c[1])
                                        for c in sub_categories if c != 0]))
        return filter_url

    @classmethod
    def get_response_json(cls, requests, search_string, auth_handler, config):
        """get_response_json.

        Return json object from request on torrent411 api

        :param requests: requests object
        :param search_string: string to search
        :param auth_handler: request AuthBase object
        :param config: dict config from params
        :returns: json object, search result with t411 api
        """
        filter_url = cls.get_filter_url(config.get('category'),
                                        config.get('sub_category'))

        query = normalize_unicode(search_string)
        url_search = ('/torrents/search/' + quote_plus(query.encode('utf-8')) +
                      filter_url)

        try:
            response = requests.get(BASE_URL + url_search, auth=auth_handler)
        except requests.exceptions.RequestException as exc:
            raise plugin.PluginError(exc)

        res_json = response.json()

        if 'errors' in res_json.keys():
            auth_handler = T411Auth(requests, config.get('username'),
                                    config.get('password'), force_auth=True)
            try:
                res_json = requests.get(BASE_URL + url_search,
                                        auth=auth_handler).json()
            except requests.exceptions.RequestException as exc:
                raise plugin.PluginError(exc)

            if 'errors' in res_json.keys():
                raise plugin.PluginError(res_json['error'])

        return res_json

    @classmethod
    @plugin.internet(log)
    def search(cls, task, entry, config=None):
        """search.

        :param task: task object
        :param entry: entry object
        :param config: dict from params
        :returns: set of entry
        """
        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):
            auth_handler = T411Auth(task.requests,
                                    config.get('username'),
                                    config.get('password'))

            res_json = cls.get_response_json(task.requests, search_string,
                                             auth_handler, config)

            for torrent in res_json['torrents']:
                entries.add(cls.get_entry(torrent, auth_handler))

        return sorted(entries, reverse=True,
                      key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    """register_plugin."""
    plugin.register(SearchT411, 't411',
                    groups=['search'],
                    api_ver=2)
