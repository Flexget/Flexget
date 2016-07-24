from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from datetime import datetime
from functools import partial
import json
import logging
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils import qualities
from flexget.utils.database import with_session
from requests.auth import AuthBase

from sqlalchemy import (Table, Column, Integer, String, ForeignKey, DateTime, Boolean)
from sqlalchemy.orm import relation, backref
from flexget import db_schema
from flexget.utils.requests import Session
from sqlalchemy.orm.exc import NoResultFound

log = logging.getLogger('t411_api')

# region ORM definitions
SCHEMA_VER = 0
Base = db_schema.versioned_base('t411', SCHEMA_VER)
category_term_types = Table('category_term_types', Base.metadata,
                            Column('category_id', Integer, ForeignKey('categories.id')),
                            Column('term_type_id', Integer, ForeignKey('term_types.id')))
Base.register_table(category_term_types)

torrent_terms = Table('torrent_terms', Base.metadata,
                      Column('torrent_id', Integer, ForeignKey('torrent.id')),
                      Column('term_id', Integer, ForeignKey('term.id')))
Base.register_table(torrent_terms)


@db_schema.upgrade('t411')
def upgrade(ver, session):
    return SCHEMA_VER


class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    sub_categories = relation('Category',
                              backref=backref('parent', remote_side=[id]),
                              cascade='all, delete, delete-orphan')
    term_types = relation('TermType',
                          secondary=category_term_types,
                          backref='categories')
    torrents = relation('Torrent',
                        backref='category',
                        cascade='all, delete, delete-orphan')


class TermType(Base):
    __tablename__ = 'term_types'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    mode = Column(String)
    terms = relation('Term',
                     backref='type',
                     cascade='all, delete, delete-orphan')


class Term(Base):
    __tablename__ = 'term'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_id = Column(Integer, ForeignKey('term_types.id'))


class Torrent(Base):
    """
    Immutable torrent informations
    """
    __tablename__ = 'torrent'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    rewrite_name = Column(String)
    category_id = Column(Integer, ForeignKey('categories.id'))
    terms = relation('Term',
                     secondary='torrent_terms',
                     backref='torrents')
    owner = Column(Integer)
    username = Column(String)


class TorrentStatus(Base):
    __tablename__ = 'torrent_status'
    id = Column(Integer, primary_key=True)
    torrent_id = Column(Integer, ForeignKey('torrent.id'))
    timestamp = Column(DateTime)


class Credential(Base):
    __tablename__ = 'credential'
    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    api_token = Column(String)
    default = Column(Boolean, nullable=False, default=False)


# endregion ORM definition


class FriendlySearchQuery(object):

    def __init__(self):
        self.expression = None
        self.category_name = None
        self.term_names = []
        self.max_results = 10

    def add_season_term(self, season):
        self.term_names.append("Saison %02d" % season)

    def add_episode_term(self, episode):
        self.term_names.append("Episode %02d" % episode)


T411API_DOMAIN_URL = "api.t411.ch"
T411API_CATEGORY_TREE_PATH = "/categories/tree/"
T411API_AUTH_PATH = "/auth"
T411API_TERMS_PATH = "/terms/tree/"
T411API_SEARCH_PATH = "/torrents/search/"
T411API_DOWNLOAD_PATH = "/torrents/download/"
T411API_DETAILS_PATH = "/torrents/details/"
T411_TERM_TYPE_ID_VIDEO_QUALITY = 7

T411_VIDEO_QUALITY_MAP = {
    8: qualities.get("bluray"),
    1171: qualities.get("bluray"),
    17: qualities.get("bluray 1080p"),
    1220: qualities.get("remux"),
    13: qualities.get("dvdrip"),
    14: qualities.get("dvdrip"),
    10: qualities.get("dvdrip"),
    1208: qualities.get("bluray 1080p"),
    1218: qualities.get("bluray 720p"),
    16: qualities.get("bluray 1080p"),
    1219: qualities.get("bluray"),
    15: qualities.get("bluray 720p"),
    11: qualities.get("tvrip"),
    1162: qualities.get("hdtv 1080p"),
    12: qualities.get("hdtv 720p"),
    18: qualities.get("ppvrip"),
    1233: qualities.get("webdl"),
    1174: qualities.get("webdl 1080p"),
    1182: qualities.get("webdl"),
    1175: qualities.get("webdl 720p"),
    19: qualities.get("webrip")
}


def auth_required(func):
    """
    Decorator for ensuring rest client is authenticated
    or will doing it before execute the command
    :param func:
    :return:
    """

    def wrapper(self, *args, **kwargs):
        if not self.is_authenticated():
            log.debug('None API token. Authenticating with "%s" account...', self.credentials.get('username'))
            self.auth()
            assert self.is_authenticated()
        return func(self, *args, **kwargs)

    return wrapper


class ApiError(Exception):
    """
    Exception raise when RestClient received a business error
    from T411 server.
    """

    def __init__(self, code, description):
        self.description = description
        self.code = code


class T411RestClient(object):
    """A REST client for T411 API"""

    @staticmethod
    def template_url(url_scheme='http'):
        return url_scheme + '://' + T411API_DOMAIN_URL + '%s'

    @staticmethod
    def download_url(torrent_id, url_scheme='http'):
        return (T411RestClient.template_url(url_scheme) % T411API_DOWNLOAD_PATH) + str(torrent_id)

    def __init__(self, username=None, password=None, url_scheme='http'):
        self.credentials = {'username': username, 'password': password}
        self.api_token = None
        self.api_template_url = url_scheme + '://' + T411API_DOMAIN_URL + '%s'
        self.web_session = Session()

    def auth(self):
        """
        Request server to obtain a api token. Obtained
        token will be set for future usage of the client instance
        :return:
        """
        auth_url = self.api_template_url % T411API_AUTH_PATH
        response = self.web_session.post(auth_url, self.credentials)
        json_response = response.json()
        error_description = json_response.get('error', None)
        if error_description:
            log.error('%d - %s', json_response.get('code'), error_description)
        else:
            self.set_api_token(json_response.get('token'))

    def set_api_token(self, api_token):
        """
        Set the client for use an api token.
        :param api_token:
        :return:
        """
        self.api_token = api_token
        self.web_session.headers.update({'Authorization': self.api_token})

    def is_authenticated(self):
        """
        :return: True if an api token is set. Note that the client
        doesn't check if the token is valid (expired or wrong).
        """
        return self.api_token is not None

    @staticmethod
    def raise_on_fail_response(json_response):
        """
        This method throw an Exception if server return a
        error message
        :return:
        """
        if json_response is None:
            pass

        error_name = json_response.get('error', None)
        error_code = json_response.get('code', None)
        if error_name is not None:
            raise ApiError(error_code, error_name)

    def get_json(self, path, params=None):
        """
        Common method for requesting JSON response
        :param path:
        :return:
        """
        url = self.api_template_url % path

        request = self.web_session.get(url, params=params)
        try:
            result = request.json()
        except ValueError:
            log.debug("Response from %s was not JSON encoded. Attempting deep inspection...", path)
            try:
                last_line = request.text.splitlines()[-1]
                result = json.loads(last_line)
            except (ValueError, IndexError):
                log.warning("Server response doesn't contains any JSON encoded response.")
                raise

        T411RestClient.raise_on_fail_response(result)
        return result

    @auth_required
    def retrieve_category_tree(self):
        """
        Request T411 API for retrieving categories and them
        subcategories
        :return**kwargs:
        """
        return self.get_json(T411API_CATEGORY_TREE_PATH)

    @auth_required
    def retrieve_terms_tree(self):
        """
        Request T411 API for retrieving term types
        and terms
        :return **kwargs:
        """
        return self.get_json(T411API_TERMS_PATH)

    @auth_required
    def search(self, query):
        """
        Search torrent
        :param query: dict
        :param query['category_id']: Int optional
        :param query['result_per_page']: Int optional
        :param query['page_index']: Int optional
        :param query['terms']: (Term type id, Term id,)
        :return dict
        """
        url = T411API_SEARCH_PATH
        if query.get('expression') is not None:
            url += query['expression']

        url_params = {}
        if query.get('category_id') is not None:
            # using cat or cid will do the same result
            # but using cid without query expression will not broke
            # results
            url_params['cid'] = query['category_id']
        if query.get('result_per_page') is not None:
            url_params['limit'] = query['result_per_page']
        if query.get('page_index') is not None:
            url_params['offset'] = query['page_index']
        if query.get('terms') is not None:
            for (term_type_id, term_id) in query['terms']:
                term_type_key_param = 'term[%s][]' % term_type_id

                if url_params.get(term_type_key_param) is None:
                    url_params[term_type_key_param] = []

                url_params[term_type_key_param].append(term_id)
        return self.get_json(url, params=url_params)

    @auth_required
    def details(self, torrent_id):
        url = T411API_DETAILS_PATH + str(torrent_id)
        return self.get_json(url)


class T411ObjectMapper(object):
    """
    Tool class to convert JSON object from the REST client
    into object for ORM
    """
    date_format = "%Y-%m-%d %H:%M:%S"

    def map_category(self, json_category):
        """
        Parse one JSON object of a category (and its subcategories) to Category
        :param json_category: dict
        :return:
        """

        # Some categories are empty, so we reject them
        if json_category.get('id') is None \
                or json_category.get('pid') is None \
                or json_category.get('name') is None:
            return None

        mapped_category = Category()
        mapped_category.id = int(json_category.get(u'id'))
        pid = int(json_category.get(u'pid'))
        if pid == 0:
            mapped_category.parent_id = None
        else:
            mapped_category.parent_id = pid
        mapped_category.name = json_category.get(u'name')

        json_sub_categories = json_category.get(u'cats')
        if json_sub_categories is not None:
            for json_sub_category in json_sub_categories.values():
                mapped_sub_category = self.map_category(json_sub_category)
                mapped_category.sub_categories.append(mapped_sub_category)

        return mapped_category

    def map_category_tree(self, json_category_tree):
        """
        :param json_category_tree: dict
        :return array of main Category, dict of [Integer, Category]
        """
        indexed_categories = {}
        main_categories = []
        for json_main_category in json_category_tree.values():
            main_category = self.map_category(json_main_category)
            if main_category is not None:
                main_categories.append(main_category)
                indexed_categories[main_category.id] = main_category
                for sub_category in main_category.sub_categories:
                    indexed_categories[sub_category.id] = sub_category

        return main_categories, indexed_categories

    @staticmethod
    def map_term_type_tree(json_tree):
        """
        :param json_tree: dict
        :return: (array of tupple, dict of TermType)
        """
        # term type definition can appears multiple times
        category_to_term_type = []  # relations category-term type
        term_types = {}  # term types, indexed by termtype id
        terms = {}  # terms, indexed by id
        for category_key, json_term_types in json_tree.items():
            for term_type_key, term_type_content in json_term_types.items():
                term_type_id = int(term_type_key)
                category_to_term_type.append((int(category_key), term_type_id))

                # if a term type has already parsed
                # then we just record the category-term type relation
                if term_type_id not in term_types:
                    term_type = TermType()
                    term_type.id = term_type_id
                    term_type.name = term_type_content.get('type')
                    term_type.mode = term_type_content.get('mode')
                    term_types[term_type.id] = term_type  # index term type
                    for term_id, term_name in term_type_content.get('terms').items():
                        # Parsing & indexing terms
                        if term_id not in terms:
                            term = Term(id=int(term_id), name=term_name)
                            term_type.terms.append(term)

        return category_to_term_type, term_types

    @staticmethod
    def map_search_result_entry(json_entry, download_auth=None):
        """
        Parse json object of a torrent entry to flexget Entry
        :param download_auth: Requests authenticator
        """
        result = Entry()
        result['t411_torrent_id'] = int(json_entry['id'])
        result['title'] = json_entry['name']
        result['url'] = T411RestClient.download_url(json_entry['id'])
        result['t411_category'] = int(json_entry['category'])
        result['seeders'] = int(json_entry['seeders'])
        result['leechers'] = int(json_entry['leechers'])
        result['t411_comments'] = int(json_entry['comments'])
        result['t411_verified'] = json_entry['isVerified'] is '1'
        result['t411_pubdate'] = datetime.strptime(json_entry['added'], T411ObjectMapper.date_format)
        result['content_size'] = int(json_entry['size']) / (1024 ** 2)
        result['t411_times_completed'] = int(json_entry['times_completed'])
        result['t411_category_name'] = json_entry['categoryname']
        result['t411_category_image'] = json_entry['categoryimage']
        result['t411_privacy'] = json_entry['privacy']
        result['t411_owner_id'] = int(json_entry['owner'])
        result['t411_owner_username'] = json_entry['username']
        result['download_auth'] = download_auth
        return result

    @staticmethod
    def map_details(json_details, resolver):
        """
        Parse json entry of details of a torrent entry
        to Torrent object.
        """
        result = Torrent()
        result.id = json_details.get('id')
        result.name = json_details.get('name')
        result.category_id = json_details.get('category')

        # Parse collection of termtype-termvalue
        for (term_type_name, terms_candidat) in json_details.get('terms').items():
            if isinstance(terms_candidat, list):
                # Some terms type are multi-valuable, eg. Genres
                for term_name in terms_candidat:
                    term_entity = resolver(result.category_id, term_type_name, term_name)
                    if term_entity is not None:
                        result.terms.append(term_entity)
            else:
                term_entity = resolver(result.category_id, term_type_name, terms_candidat)
                if term_entity is not None:
                    result.terms.append(term_entity)

        return result


def cache_required(func):
    """
    Decorator for ensuring cached data into db.
    If not a synchronize will be launched
    :param func:
    :return:
    """

    def wrapper(self, *args, **kwargs):
        if not self.has_cached_criterias():
            log.debug('None cached data. Synchronizing...')
            self.synchronize_database()
        return func(self, *args, **kwargs)

    return wrapper


class T411Proxy(object):
    """
    A T411 proxy service. This proxy interact both with
    T411 Rest Client and T411 local database.
    """

    def __init__(self, session=None):
        """
        :param session: flexget.manager.Session
        """
        self.rest_client = T411RestClient()
        self.mapper = T411ObjectMapper()
        self.__has_cached_criterias = None

    def __set_credential(self, username=None, password=None, api_token=None):
        self.rest_client.api_token = api_token
        self.rest_client.credentials = {
            'username': username,
            'password': password
        }

    @with_session
    def set_credential(self, username=None, session=None):
        """
        Set REST client credential from database
        :param username: if set, account's credential will be used.
        :return:
        """
        query = session.query(Credential)
        if username:
            query = query.filter(Credential.username == username)
        credential = query.first()

        if credential is None:
            raise PluginError('You cannot use t411 plugin without credentials. '
                              'Please set credential with "flexget t411 add-auth <username> <password>".')
        self.__set_credential(credential.username, credential.password, credential.api_token)

    @with_session
    def has_cached_criterias(self, session=None):
        """
        :return: True if database contains data of a previous synchronization
        """
        if self.__has_cached_criterias is None:
            self.__has_cached_criterias = session.query(Category).count() > 0
        return self.__has_cached_criterias

    @with_session
    def synchronize_database(self, session=None):
        """
        If database has been cleaned, this method
        will update it.
        :return:
        """
        log.debug('T411Proxy start database synchronization with T411')
        category_tree = self.rest_client.retrieve_category_tree()
        term_tree = self.rest_client.retrieve_terms_tree()

        main_categories, indexed_categories = self.mapper.map_category_tree(category_tree)
        category_to_term_type, term_types = self.mapper.map_term_type_tree(term_tree)
        log.debug('%d categories (%d are main categories) and %d term types retrieved',
                  len(indexed_categories),
                  len(main_categories),
                  len(term_types))
        for (category_id, term_type_id) in category_to_term_type:
            category = indexed_categories.get(category_id)
            term_type = term_types.get(term_type_id)
            category.term_types.append(term_type)

        session.add_all(main_categories)
        session.commit()
        self.__has_cached_criterias = None

    @cache_required
    @with_session
    def find_categories(self, category_name=None, is_sub_category=False, session=None):
        query = session.query(Category)
        if category_name is not None:
            query = query.filter(Category.name == category_name)
        if is_sub_category:
            query = query.filter(Category.parent_id.isnot(None))
        return query.all()

    @cache_required
    @with_session
    def find_term_types(self, category_id=None, term_type_name=None, session=None):
        query = session.query(TermType) \
            .filter(TermType.name == term_type_name) \
            .filter(TermType.categories.any(Category.id == category_id))
        return query.one()

    @cache_required
    @with_session
    def find_term_by_name(self, term_type_id, term_name, session=None):
        return session.query(Term) \
            .filter(Term.type_id == term_type_id) \
            .filter(Term.name == term_name) \
            .one()

    @cache_required
    @with_session
    def find_term(self, category_id, term_type_name, term_name, session=None):
        result = session.query(Term) \
            .filter(Term.type.has(TermType.categories.any(Category.id == category_id))) \
            .filter(Term.type.has(TermType.name == term_type_name)) \
            .filter(Term.name == term_name) \
            .first()
        return result

    @cache_required
    @with_session
    def main_categories(self, session=None):
        query = session.query(Category).filter(Category.parent_id.is_(None))
        return query.all()

    @cache_required
    @with_session
    def all_category_names(self, categories_filter='all', session=None):
        name_query = session.query(Category.name)
        if categories_filter == 'sub':
            name_query.filter(Category.parent_id is not None)
        elif categories_filter == 'main':
            name_query.filter(Category.parent_id is None)

        return [name for (name,) in name_query.all()]

    @cache_required
    @with_session
    def all_term_names(self, session=None):
        name_query = session.query(Term.name).all()
        return [name for (name,) in name_query]

    @cache_required
    @with_session
    def friendly_query_to_client_query(self, friendly_query, session=None):
        """
        :param FriendlySearchQuery query:
        :return (,)[]: T411RestClient.search compatible
        """
        client_query = {'expression': friendly_query.expression}

        if friendly_query.category_name is not None:
            try:
                (category_id,) = session \
                    .query(Category.id) \
                    .filter(Category.name == friendly_query.category_name) \
                    .one()
                client_query['category_id'] = category_id
                log.debug('Category named "%s" resolved by id %d', friendly_query.category_name, category_id)

                if len(friendly_query.term_names) > 0:
                    log.debug('Resolving terms : %s' % friendly_query.term_names)
                    or_like = (Term.name.like(friendly_query.term_names[0] + '%'))
                    for term_name in friendly_query.term_names[1:]:
                        or_like |= (Term.name.like(term_name + '%'))

                    client_query['terms'] = session \
                        .query(Term.type_id, Term.id) \
                        .filter(or_like) \
                        .filter(TermType.categories.any(Category.id == category_id)) \
                        .filter(Term.type_id == TermType.id).all()
            except NoResultFound:
                log.warning('Unable to resolve category named %s', friendly_query.category_name)
                log.warning('Terms filter will be passed')

        if friendly_query.max_results is not None:
            client_query['result_per_page'] = friendly_query.max_results
            client_query['page_index'] = 0

        return client_query

    def search(self, query):
        """
        :param FriendlySearchQuery query:
        :return:
        """
        client_query = self.friendly_query_to_client_query(query)
        json_results = self.rest_client.search(client_query)
        json_torrents = json_results.get('torrents', [])
        json_not_pending_torrents = [x for x in json_torrents if not isinstance(x, int)]
        log.debug("Search produces %d results including %d 'on pending' (the latter will not produces entries)",
                  len(json_torrents),
                  len(json_torrents) - len(json_not_pending_torrents))
        download_auth = T411BindAuth(self.rest_client.api_token)

        map_function = partial(T411ObjectMapper.map_search_result_entry, download_auth=download_auth)
        return list(map(map_function, json_not_pending_torrents))

    @cache_required
    @with_session
    def details(self, torrent_id, session=None):
        """
        WIP
        Download and store torrent details
        :param torrent_id:
        :return:
        """
        details = session \
            .query(Torrent) \
            .filter(Torrent.id == torrent_id) \
            .first()
        if details:
            return details
        else:
            log.debug('Torrent %d cache miss. Online retrieving...', torrent_id)
            # Cache dismiss, retrieve details via online way
            json_details = self.rest_client.details(torrent_id)

            def resolver(category_id, term_type_name, term_name):
                return self.find_term(category_id, term_type_name, term_name, session=session)

            details = self.mapper.map_details(json_details, resolver)
            session.add(details)
            session.commit()
            return details

    @with_session
    def add_credential(self, username, password, session=None):
        """
        Add a credential
        :param username:    T411 username
        :param password:    T411 password
        :return:    False if username still has an entry (password has been updated)
        """
        credential = session.query(Credential).filter(Credential.username == username).first()
        if credential:
            credential.password = password
            credential.api_token = None
            result = False
        else:
            credential = Credential(username=username, password=password)
            session.add(credential)
            result = True
        session.commit()
        return result

    @cache_required
    @with_session
    def parse_terms_to_quality(self, terms, session=None):
        """
        If terms contains a term with the termtype 'video quality'
        then this function convert it into a flexget Quality
        else it return None
        :param terms: Array of Term
        :param session:
        :return: flexget.utils.Quality
        """
        video_quality_description = next((
            term for term in terms
            if term.get('term_type_id') == T411_TERM_TYPE_ID_VIDEO_QUALITY), None)
        if video_quality_description is not None:
            video_quality = T411_VIDEO_QUALITY_MAP.get(video_quality_description.get('term_id'))
            return video_quality
        else:
            return None


class T411BindAuth(AuthBase):

    def __init__(self, api_token):
        self.api_token = api_token

    def __call__(self, request):
        request.headers['authorization'] = self.api_token
        return request


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    session.query(Category).delete(synchronize_session=False)
    session.query(TermType).delete(synchronize_session=False)
    session.query(Term).delete(synchronize_session=False)
