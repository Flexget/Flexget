from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import json
import logging
import urllib
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.database import with_session

from sqlalchemy import (Table, Column, Integer, String, ForeignKey, DateTime)
from sqlalchemy.orm import relation, backref
from flexget import db_schema
from flexget.utils.requests import Session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

log = logging.getLogger('t411')

# region ORM definitions
SCHEMA_VER = 0
Base = db_schema.versioned_base('t411', SCHEMA_VER)
category_term_types = Table('category_term_types', Base.metadata,
                            Column('category_id', Integer, ForeignKey('categories.id')),
                            Column('term_type_id', Integer, ForeignKey('term_types.id')))

torrent_terms = Table('torrent_terms', Base.metadata,
                      Column('torrent_id', Integer, ForeignKey('torrent.id')),
                      Column('term_id', Integer, ForeignKey('term.id')))

@db_schema.upgrade('api_t411')
def upgrade(ver, session):
    assert ver is None or ver <= SCHEMA_VER
    return ver


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
# endregion ORM definition


class FriendlySearchQuery(object):
    def __init__(self):
        self.expression = None
        self.category_name = None
        self.term_names = []
        self.max_results = 10

T411API_DOMAIN_URL = "api.t411.in"
T411API_CATEGORY_TREE_PATH = "/categories/tree/"
T411API_AUTH_PATH = "/auth"
T411API_TERMS_PATH = "/terms/tree/"
T411API_SEARCH_PATH = "/torrents/search/"
T411API_DOWNLOAD_PATH = "/torrents/download/"
T411API_DETAILS_PATH = "/torrents/details/"
T411_VIDEO_QUALITY_TERM_TYPE = 7


def auth_required(func):
    """
    Decorator for ensuring rest client is authenticated
    or will doing it before execute the command
    :param func:
    :return:
    """
    def wrapper(self, *args, **kwargs):
        if not self.is_authenticated():
            log.debug('None API token. Authenticating...')
            self.auth()
            assert self.is_authenticated()
        return func(self, *args, **kwargs)
    return wrapper


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
        auth_url = self.api_template_url % T411API_AUTH_PATH
        response = self.web_session.post(auth_url, self.credentials)
        json_response = response.json()
        error_description = json_response.get('error', None)
        if error_description:
            log.error('%d - %s' % (json_response.get('code'), error_description))
        else:
            self.set_api_token(json_response.get('token'))

    def set_api_token(self, api_token):
        self.api_token = api_token
        self.web_session.headers.update({'Authorization': self.api_token})

    def is_authenticated(self):
        return self.api_token is not None

    def get_json(self, path):
        """
        Common method for requesting JSON response
        :param path:
        :return:
        """
        url = self.api_template_url % path
        request = self.web_session.get(url)
        try:
            result = request.json()
        except ValueError:
            log.debug("Response from %s was not JSON encoded. Attempting deep inspection..." % path)
            try:
                last_line = request.text.splitlines()[-1]
                result = json.loads(last_line)
            except (ValueError, IndexError) as e:
                log.warning("Server response doesn't contains any JSON encoded response.")
                return None

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
        url = T411API_SEARCH_PATH
        if query.get('expression') is not None:
            url += query['expression']
        url += '?'

        url_params = []
        if query.get('category_id') is not None:
            url_params.append(('cat', query['category_id']))
        if query.get('result_per_page') is not None:
            url_params.append(('limit', query['result_per_page']))
        if query.get('page_index') is not None:
            url_params.append(('offset', query['page_index']))
        if query.get('terms') is not None:
            url_params.extend([('term[' + str(term_type_id) + '][]', term_id)
                               for (term_type_id, term_id) in query['terms']])

        url += urllib.urlencode(url_params)
        return self.get_json(url)

    @auth_required
    def details(self, torrent_id):
        url = T411API_DETAILS_PATH + torrent_id
        return self.get_json(url)


class T411ObjectMapper(object):
    date_format = "%Y-%m-%d %H:%M:%S"

    """
    Tool class to convert JSON object from the REST client
    into object for ORM
    """
    def map_category(self, json_category):
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
            for json_sub_category in json_sub_categories.itervalues():
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
        for json_main_category in json_category_tree.itervalues():
            main_category = self.map_category(json_main_category)
            if main_category is not None:
                main_categories.append(main_category)
                indexed_categories[main_category.id] = main_category
                for sub_category in main_category.sub_categories:
                    indexed_categories[sub_category.id] = sub_category

        return main_categories, indexed_categories

    def map_term_type(self, term_type_id, json_term_type):
        """
        Parse to TermType a json Term type
        :param term_type_id: int
        :param json_term_type: dict
        :return:
        """
        term_type = TermType()
        term_type.id = term_type_id
        term_type.name = json_term_type.get('type')
        term_type.mode = json_term_type.get('mode')
        for term_id, term_name in json_term_type.get('terms').iteritems():
            term = Term(id=int(term_id), name=term_name)
            term_type.terms.append(term)
        return term_type

    def map_term_type_tree(self, json_tree):
        """
        :param json_tree: dict
        :return: (array of tupple, dict of TermType)
        """
        # term type definition can appears multiple times
        category_to_term_type = []  # relations category-term type
        term_types = {}  # term types, indexed by termtype id
        for category_key, json_term_types in json_tree.iteritems():
            for term_type_key, term_type_content in json_term_types.iteritems():
                term_type_id = int(term_type_key)
                category_to_term_type.append((int(category_key), term_type_id))

                # if a term type has already parsed
                # then we just record the category-term type relation
                if term_type_id not in term_types:
                    term_type = self.map_term_type(term_type_id, term_type_content)
                    term_types[term_type.id] = term_type

        return category_to_term_type, term_types

    def map_search_result_entry(self, json_entry):
        result = Entry()
        result['t411_torrent_id'] = json_entry['id']
        result['title'] = json_entry['name']
        result['url'] = T411RestClient.download_url(json_entry['id'])
        result['t411_category'] = int(json_entry['category'])
        result['seeders'] = int(json_entry['seeders'])
        result['leechers'] = int(json_entry['leechers'])
        result['t411_comments'] = int(json_entry['comments'])
        result['t411_isVerified'] = json_entry['isVerified'] is '1'
        result['t411_pubdate'] = datetime.strptime(json_entry['added'], self.date_format)
        result['content_size'] = int(json_entry['size'])
        result['t411_times_completed'] = int(json_entry['times_completed'])
        result['t411_category_name'] = json_entry['categoryname']
        result['t411_category_image'] = json_entry['categoryimage']
        result['t411_privacy'] = json_entry['privacy']
        result['t411_owner_id'] = int(json_entry['owner'])
        result['t411_owner_username'] = json_entry['username']
        return result

    def map_details(self, json_details, resolver):
        result = Torrent()
        result.id = json_details.get('id')
        result.name = json_details.get('name')
        result.category_id = json_details.get('category')

        for (term_type_name, terms_candidat) in json_details.get('terms').iteritems():
            if isinstance(terms_candidat, list):
                for term_name in terms_candidat:
                    result.terms.append(resolver(result.category_id, term_type_name, term_name))
            else:
                result.terms.append(resolver(result.category_id, term_type_name, terms_candidat))

        return result


def cache_required(func):
    """
    Decorator for ensuring cached data into db.
    Ifnot a synchronize will be launched
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
    @with_session
    def __init__(self, username=None, password=None, session=None):
        """
        :param username: String
        :param password: String
        :param session: flexget.manager.Session
        """
        self.session = session
        self.rest_client = T411RestClient(username, password)
        self.mapper = T411ObjectMapper()
        self.__has_cached_criterias = None

    def set_credentials(self, username, password):
        self.rest_client.api_token = None
        self.rest_client.credentials = {
            'username': username,
            'password': password
        }

    def has_cached_criterias(self):
        """
        :return: True if database contains previous version of criterias
        """
        if self.__has_cached_criterias is None:
            self.__has_cached_criterias = self.session.query(Category).count() > 0
        return self.__has_cached_criterias

    def synchronize_database(self):
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
        log.debug('%d categories (%d are main categories) and %d term types retrieved'
                  % (len(indexed_categories), len(main_categories), len(term_types)))
        for (category_id, term_type_id) in category_to_term_type:
            category = indexed_categories.get(category_id)
            term_type = term_types.get(term_type_id)
            category.term_types.append(term_type)

        self.session.add_all(main_categories)
        self.session.commit()
        self.__has_cached_criterias = None

    @cache_required
    def find_category_by_name(self, category_name):
        query = self.session.query(Category).filter(Category.name == category_name)
        try:
            category = query.one()
        except MultipleResultsFound:
            log.warning('The category "%s" has more than one id ; first will be use. '
                        'Please report this incident on Flexget.com' % category_name)
            category = query.first()
        except NoResultFound:
            log.warning('None result found for a category named "%s"' % category_name)
            return None
        return category

    @cache_required
    def find_term_type_by_name(self, category_id, term_type_name):
        query = self.session.query(TermType)\
            .filter(TermType.name == term_type_name) \
            .filter(TermType.categories.any(Category.id == category_id))
        return query.one()

    @cache_required
    def find_term_by_name(self, term_type_id, term_name):
        return self.session.query(Term)\
            .filter(Term.type_id == term_type_id)\
            .filter(Term.name == term_name)\
            .one()

    @cache_required
    def find_term(self, category_id, term_type_name, term_name):
        return self.session.query(Term) \
            .filter(TermType.name == term_type_name) \
            .filter(TermType.categories.any(Category.id == category_id)) \
            .filter(TermType.terms.any(Term.name == term_name)) \
            .first()

    @cache_required
    def all_categories(self):
        return self.session.query(Category).all()

    @cache_required
    def all_category_names(self):
        name_query = self.session.query(Category.name).all()
        return [name for (name,) in name_query]

    @cache_required
    def all_term_names(self):
        name_query = self.session.query(Term.name).all()
        return [name for (name,) in name_query]

    @cache_required
    def print_categories(self):
        categories = self.session.query(Category).filter(Category.parent_id == None).all()
        formatting_main = '%-30s %-5s %-5s'
        formatting_sub = '     %-25s %-5s %-5s'
        log.debug(formatting_main % ('Name', 'PID', 'ID'))
        for category in categories:
            log.debug(formatting_main % (category.name, category.parent_id, category.id))
            for sub_category in category.sub_categories:
                log.debug(formatting_sub % (sub_category.name, sub_category.parent_id, sub_category.id))

    @cache_required
    def print_all_terms(self):
        formatting_main = '%-50s %-10s %-5s'
        formatting_sub = '     %-45s %-10s %-5s'
        term_types = self.session.query(TermType).all()
        log.debug(formatting_main % ('Name', 'Mode', 'Id'))
        for term_type in term_types:
            log.debug(formatting_main % (term_type.name, term_type.mode, term_type.id))
            for term in term_type.terms:
                log.debug(formatting_sub % (term.name, '', term.id))

    @cache_required
    def print_terms(self, category_id=None, category_name=None):
        if category_id is not None:
            category = self.session.query(Category).filter(Category.id == category_id).one()
        elif category_name is not None:
            category = self.find_category_by_name(category_name)
        else:
            self.print_all_terms()
            return

        log.debug('Terms for the category %s' % category.name)
        formatting_main = '%-50s %-10s %-5s'
        formatting_sub = '     %-45s %-10s %-5s'
        log.debug(formatting_main % ('Name', 'Mode', 'Id'))
        for term_type in category.term_types:
            log.debug(formatting_main % (term_type.name, term_type.mode, term_type.id))
            for term in term_type.terms:
                log.debug(formatting_sub % (term.name, '', term.id))

    @cache_required
    def friendly_query_to_client_query(self, friendly_query):
        """
        :param FriendlySearchQuery query:
        :return (,)[]: T411RestClient.search compatible
        """
        client_query = {'expression': friendly_query.expression}

        if friendly_query.category_name is not None:
            try:
                (category_id,) = self.session \
                    .query(Category.id) \
                    .filter(Category.name == friendly_query.category_name) \
                    .one()
                client_query['category_id'] = category_id
                log.debug('Category named "%s" resolved by id %d' % (friendly_query.category_name, category_id))

                client_query['terms'] = self.session \
                    .query(Term.type_id, Term.id) \
                    .filter(Term.name.in_(friendly_query.term_names)) \
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
        log.debug("Search produces %d results." % len(json_torrents))
        return map(self.mapper.map_search_result_entry, json_torrents)

    @cache_required
    def details(self, torrent_id):
        details = self.session \
                    .query(Torrent) \
                    .filter(Torrent.id == torrent_id) \
                    .first()
        if details:
            return details
        else:
            json_details = self.rest_client.details(torrent_id)

            def resolver(category_id, term_type_name, term_name):
                return self.find_term(category_id, term_type_name, term_name)

            details = self.mapper.map_details(json_details, resolver)
            self.session.add(details)
            self.session.commit()
            return details

@event('manager.db_cleanup')
def db_cleanup(manager, session):
    session.query(Category).delete(synchronize_session=False)
    session.query(TermType).delete(synchronize_session=False)