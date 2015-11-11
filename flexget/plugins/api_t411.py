from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from abc import abstractmethod, abstractproperty
from abc import ABCMeta
from flexget.utils.database import with_session
from flexget.utils.log import log_once
from sqlalchemy import (Table, Column, Integer, String, Unicode, DateTime, desc, ForeignKey)
from sqlalchemy.orm import relation, backref
import flexget.manager
from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.requests import Session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

log = logging.getLogger('t411')

# region ORM definitions
SCHEMA_VER = 0
Base = db_schema.versioned_base('t411', SCHEMA_VER)
category_term_types = Table('category_term_types', Base.metadata,
                            Column('category_id', Integer, ForeignKey('categories.id')),
                            Column('term_type_id', Integer, ForeignKey('term_types.id')))


@db_schema.upgrade('t411')
def upgrade(ver, session):
    if ver is None:
        log.debug('Creating T411 database.')
    return 0


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


class TermType(Base):
    __tablename__ = 'term_types'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    mode = Column(String)


class Term(Base):
    __tablename__ = 'term'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_id = Column(Integer, ForeignKey('term_types.id'))
    type = relation('TermType',
                    backref='terms')


T411API_DOMAIN_URL = "api.t411.in"
T411API_CATEGORY_TREE_PATH = "/categories/tree/"
T411API_AUTH_PATH = "/auth"
T411API_TERMS_PATH = "/terms/tree/"
T411API_SEARCH_PATH = "/torrents/search/"


class T411RestClient(object):
    """A REST client for T411 API"""

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
            self.api_token = json_response.get('token')
            self.web_session.headers.update({'Authorization': self.api_token})
            log.debug('Successfully authenticated')

    def is_authenticated(self):
        return self.api_token is not None

    def get_json(self, path):
        assert self.is_authenticated()
        url = self.api_template_url % path
        result = self.web_session.get(url).json()
        return result

    def retrieve_category_tree(self):
        """
        Request T411 API for retrieving categories and them
        subcategories
        :return: **kwargs
        """
        return self.get_json(T411API_CATEGORY_TREE_PATH)

    def retrieve_terms_tree(self):
        """
        Request T411 API for retrieving term types
        and terms
        :return: **kwargs
        """
        return self.get_json(T411API_TERMS_PATH)


class T411ObjectMapper(object):
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


class T411Proxy(object):
    """
    A T411 proxy service. This proxy interact both with
    T411 Rest Client and T411 local database.
    """

    def __init__(self, username, password, session):
        """
        :param username: String
        :param password: String
        :param session: flexget.manager.Session
        """
        self.rest_client = T411RestClient(username, password)
        self.mapper = T411ObjectMapper()
        self.session = session

    def synchronize_database(self):
        """
        If database has been cleaned, this method
        will update it.
        :return:
        """
        log.debug('T411Proxy start database synchronization with T411')
        if not self.rest_client.is_authenticated():
            self.rest_client.auth()

        log.debug('Authenticated : %s' % self.rest_client.is_authenticated())
        category_tree = self.rest_client.retrieve_category_tree()
        term_tree = self.rest_client.retrieve_terms_tree()

        main_categories, indexed_categories = self.mapper.map_category_tree(category_tree)
        category_to_term_type, term_types = self.mapper.map_term_type_tree(term_tree)
        log.debug('%d categories (%d are main categories) and %d term types retrieved'
                  % (len(indexed_categories), len(main_categories), len(term_types)))
        for (category_id, term_type_id) in category_to_term_type:
            category = indexed_categories.get(category_id)
            term_type = term_types.get(term_type_id)
            if category is not None and term_type is not None:
                category.term_types.append(term_type)
            else:
                log.warning('Zapp')

        self.session.add_all(main_categories)

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

    def print_categories(self):
        categories = self.session.query(Category).filter(Category.parent_id == None).all()
        formatting_main = '%-30s %-5s %-5s'
        formatting_sub = '     %-25s %-5s %-5s'
        log.debug(formatting_main % ('Name', 'PID', 'ID'))
        for category in categories:
            log.debug(formatting_main % (category.name, category.parent_id, category.id))
            for sub_category in category.sub_categories:
                log.debug(formatting_sub % (sub_category.name, sub_category.parent_id, sub_category.id))

    def print_terms(self, category_id=None, category_name=None):
        if category_id is None:
            category = self.find_category_by_name(category_name)
        else:
            category = self.session.query(Category).filter(Category.id == category_id).one()

        log.debug('Terms for the category %s' % category.name)
        formatting_main = '%-32s %-10s %-5s'
        formatting_sub = '     %-27s %-10s %-5s'
        log.debug(formatting_main % ('Name', 'Mode', 'Id'))
        for term_type in category.term_types:
            log.debug(formatting_main % (term_type.name, term_type.mode, term_type.id))
            for term in term_type.terms:
                log.debug(formatting_sub % (term.name, '', term.id))
