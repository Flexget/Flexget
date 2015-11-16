# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
import datetime
from __builtin__ import object
import logging
from flexget.manager import Session

from flexget.plugins.api_t411 import T411RestClient, T411ObjectMapper, T411Proxy, FriendlySearchQuery
from flexget.utils.database import with_session
from tests import use_vcr, FlexGetBase
from flexget.plugins.cli import t411

log = logging.getLogger('test_t411')


class TestRestClient(object):
    def __init__(self):
        self.credentials = {'username': '', 'password': ''}
        self.api_token = ''

    def build_unauthenticated_client(self):
        client = T411RestClient(self.credentials)
        del client.web_session.headers['Accept-Encoding']
        return client

    def build_authenticated_client(self):
        client = T411RestClient()
        client.api_token = self.api_token
        del client.web_session.headers['Accept-Encoding']
        return client

    def test_init_state(self):
        client = self.build_unauthenticated_client()
        assert not client.is_authenticated()

    @use_vcr
    def test_auth(self):
        client = self.build_unauthenticated_client()
        client.auth()
        assert client.is_authenticated(), 'Client is not authenticated (are you using mocked credentials online?)'

    @use_vcr
    def test_retrieve_categories(self):
        client = self.build_authenticated_client()
        json_tree_categories = client.retrieve_category_tree()
        json_category = json_tree_categories.get('210')
        assert json_category is not None, 'Category with id 210 wasn\'t found'
        assert json_category.get('id') == '210'
        assert json_category.get('pid') == '0'
        assert json_category.get('name') == u'Film/Vidéo'
        json_sub_categories = json_category.get('cats')
        assert json_sub_categories is not None, 'Cannot found excepted subcategories'
        json_sub_category = json_sub_categories.get('631')
        assert json_sub_category is not None
        assert json_sub_category.get('name') == 'Film'

    @use_vcr
    def test_retrieve_terms(self):
        client = self.build_authenticated_client()
        json_terms = client


class TestObjectMapper(object):
    def __init__(self):
        self.mapper = T411ObjectMapper()

    def test_map_category(self):
        category = self.mapper.map_category({
            u'pid': u'0',
            u'id': u'210',
            u'name': u'Film/Vidéo',
            u'cats': {
                u'631': {u'pid': u'210', u'id': u'631', u'name': u'Film'},
                u'633': {u'pid': u'210', u'id': u'633', u'name': u'Concert'},
                u'634': {u'pid': u'210', u'id': u'634', u'name': u'Documentaire'},
                u'635': {u'pid': u'210', u'id': u'635', u'name': u'Spectacle'},
                u'636': {u'pid': u'210', u'id': u'636', u'name': u'Sport'},
                u'637': {u'pid': u'210', u'id': u'637', u'name': u'Animation Série'},
                u'639': {u'pid': u'210', u'id': u'639', u'name': u'Emission TV'},
                u'455': {u'pid': u'210', u'id': u'455', u'name': u'Animation'},
                u'402': {u'pid': u'210', u'id': u'402', u'name': u'Vidéo-clips'},
                u'433': {u'pid': u'210', u'id': u'433', u'name': u'Série TV'}
            }
        })
        assert category.id == 210
        assert category.parent_id is None
        assert category.name == u'Film/Vidéo'
        assert len(category.sub_categories) == 10

    def test_map_term_type_tree(self):
        tree = {
            "234": {
                "11": {
                    "type": "Application - Genre",
                    "mode": "single",
                    "terms": {
                        "158": "Edition multim\u00e9dia",
                        "126": "Administration",
                        "190": "Utilitaire",
                        "169": "Lecteur multim\u00e9dia",
                        "137": "Aspiration de site",
                        "180": "Registre",
                        "148": "Communaut\u00e9"
                    }
                },
                "43": {
                    "type": "Langue",
                    "mode": "single",
                    "terms": {
                        "729": "Fran\u00e7ais",
                        "730": "Anglais",
                        "731": "Multi (Fran\u00e7ais inclus)",
                        "830": "Japonais"
                    }
                }
            }
        }
        category_to_term_type, term_types = self.mapper.map_term_type_tree(tree)
        assert (234, 11) in category_to_term_type
        assert (234, 43) in category_to_term_type
        assert term_types.has_key(11)
        assert term_types.has_key(43)
        assert term_types.get(11).mode == 'single'
        assert term_types.get(11).name == 'Application - Genre', \
            'Expected "Application - Genre", found "%s"' % term_types.get(11).name
        assert len(term_types.get(11).terms) == 7
        assert term_types.get(11).terms[0].name == "Edition multimédia"


class MockRestClient(object):
    def auth(self):
        return

    def is_authenticated(self):
        return True

    def retrieve_category_tree(self):
        return {
            "12": {  # Category ID index
                     "id": "12",  # Category ID
                     "pid": "0",  # Parent's catogory ID
                     "name": "video",
                     "cats": {  # Subcategories
                                "13": {"id": "13", "pid": "12", "name": "films"},
                                "14": {"id": "14", "pid": "12", "name": "cartoons"}
                     }
            }
        }

    def retrieve_terms_tree(self):
        return {
            "14": {  # Category ID
                     "11": {  # Term type ID
                              "type": "Application - Genre",  # Term type definition
                              "mode": "single",
                              "terms": {  # Terms of the term type
                                          "123": "Antivirus",
                                          "345": "Torrent clients"
                              }
                     }
            }
        }

    def search(self, query):
        return {
            "query": "Mickey",
            "total": 1,
            "offset": 0,
            "limit": 10,
            "torrents": [{
                 "id": 123123,
                 "name": "Mickey vs Donald",
                 "category": "14",
                 "seeders": "11",
                 "leechers": "2",
                 "comments": "8",
                 "isVerified": "1",
                 "added": "2013-01-15 16:14:14",
                 "size": "2670809119",
                 "times_completed": "1256",
                 "owner": "7589510",
                 "categoryname": "Animation",
                 "categoryimage": "t411-animation.png",
                 "username": "MegaUsername",
                 "privacy": "normal"
             }]
        }


class TestProxy(FlexGetBase):
    def test_lolcat(self):
        proxy = T411Proxy(session=Session())
        proxy.rest_client = MockRestClient()
        assert not proxy.has_cached_criterias()
        proxy.synchronize_database()
        assert proxy.has_cached_criterias()
        assert 'cartoons' in proxy.all_category_names()
        query = FriendlySearchQuery()
        query.expression = "Mickey"
        query.category_name = "cartoons"
        query.term_names.append("Antivirus")
        assert proxy.search(query)[0].category_id == 14