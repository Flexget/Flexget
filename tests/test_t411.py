# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import os

import mock
import pytest

from flexget.plugins.api_t411 import T411RestClient, T411ObjectMapper, T411Proxy, FriendlySearchQuery, ApiError
from flexget.utils.qualities import Requirements

log = logging.getLogger('test_t411')


class MockRestClient(object):
    search_result = {
        "query": "Mickey",
        "total": 1,
        "offset": 0,
        "limit": 10,
        "torrents": [{
                         "id": 123123,
                         "name": "Mickey vs Donald S01E01 1080p dd5.1 10bit",
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

    cat_result = {
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

    term_result = {
        "14": {  # Category ID
                 "11": {  # Term type ID
                          "type": "Application - Genre",  # Term type definition
                          "mode": "single",
                          "terms": {  # Terms of the term type
                                      "123": "Antivirus",
                                      "345": "Torrent clients"
                          }
                 }, "7": {
                        "type": "Vidéo - Qualité",
                        "mode": "single",
                        "terms": {"12": "TVripHD 720 [Rip HD depuis Source HD]"}
                }
        }
    }

    details_result = {
        "id": 123123,
        "name": "Mock Title 720p",
        "category": 14,
        "terms": {
            "Application - Genre": "Antivirus",
            "Vidéo - Qualité": "TVripHD 720 [Rip HD depuis Source HD]"
        }
    }

    def __init__(self):
        self.details_called = False
        self.api_token = "LOL:CAT:TOKEN"

    def auth(self):
        return

    def is_authenticated(self):
        return True

    def retrieve_category_tree(self):
        return MockRestClient.cat_result

    def retrieve_terms_tree(self):
        return MockRestClient.term_result

    def search(self, query):
        self.last_query = query
        return MockRestClient.search_result

    def details(self, torrent_id):
        assert torrent_id == 123123
        self.details_called = True
        return MockRestClient.details_result


class TestRestClient(object):
    credentials = {'username': 'set', 'password': 'this'}
    api_token = 'you must set this value for online test'

    @pytest.fixture(scope='class')
    def playback_only(self):
        if os.environ.get('VCR_RECORD_MODE') == 'off':
            pytest.skip('Cannot run this test online')

    def build_unauthenticated_client(self):
        client = T411RestClient()
        client.credentials = TestRestClient.credentials
        del client.web_session.headers['Accept-Encoding']
        return client

    def build_authenticated_client(self):
        client = T411RestClient()
        client.set_api_token(TestRestClient.api_token)
        del client.web_session.headers['Accept-Encoding']
        return client

    def test_init_state(self):
        client = self.build_unauthenticated_client()
        assert not client.is_authenticated()

    @pytest.mark.online
    def test_auth(self, playback_only):
        client = self.build_unauthenticated_client()
        client.auth()
        assert client.is_authenticated(), 'Client is not authenticated (are you using mocked credentials online?)'

    @pytest.mark.online
    def test_retrieve_categories(self, playback_only):
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

    @pytest.mark.online
    def test_retrieve_terms(self, playback_only):
        client = self.build_authenticated_client()
        json_terms = client.retrieve_terms_tree()
        assert json_terms is not None
        assert json_terms.get('234') is not None
        term_type = json_terms.get('234').get('11')
        assert term_type is not None
        assert term_type.get('type') == 'Application - Genre'
        assert term_type.get('mode') == 'single'

    @pytest.mark.online
    def test_malformed_search_response(self, playback_only):
        """
        Search without expression produces server response
        that contains some error messages. This test check
        if this case is properly handled
        :return:
        """
        client = self.build_authenticated_client()
        search_result = client.search({})
        assert search_result.get('query') is None
        assert search_result.get('limit') == 10

    @pytest.mark.online
    def test_error_message_handler(self, playback_only):
        exception_was_raised = False
        client = T411RestClient()
        client.set_api_token('LEAVE:THIS:TOKEN:FALSE')
        del client.web_session.headers['Accept-Encoding']
        try:
            client.details(666666)
        except ApiError as e:
            exception_was_raised = True
            assert e.code == 202
            pass
        assert exception_was_raised


class TestObjectMapper(object):

    def test_map_category(self):
        category = T411ObjectMapper().map_category({
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
        category_to_term_type, term_types = T411ObjectMapper().map_term_type_tree(tree)
        assert (234, 11) in category_to_term_type
        assert (234, 43) in category_to_term_type
        assert 11 in term_types
        assert 43 in term_types
        assert term_types.get(11).mode == 'single'
        assert term_types.get(11).name == 'Application - Genre', \
            'Expected "Application - Genre", found "%s"' % term_types.get(11).name
        assert len(term_types.get(11).terms) == 7
        term_names = [term.name for term in term_types.get(11).terms]
        assert "Edition multimédia" in term_names


class TestProxy(object):

    def test_offline_proxy(self):
        proxy = T411Proxy()
        proxy.rest_client = MockRestClient()
        assert not proxy.has_cached_criterias()
        proxy.synchronize_database()
        assert proxy.has_cached_criterias()
        assert 'cartoons' in proxy.all_category_names()
        query = FriendlySearchQuery()
        query.expression = "Mickey"
        query.category_name = "cartoons"
        query.term_names.append("Antivirus")
        assert proxy.search(query)[0]['t411_torrent_id'] == 123123
        assert (11,123) in proxy.rest_client.last_query['terms']
        assert proxy.rest_client.last_query['category_id'] == 14
        assert proxy.rest_client.last_query['expression'] == 'Mickey'

    def test_details(self):
        proxy = T411Proxy()
        proxy.rest_client = MockRestClient()
        details = proxy.details(123123)
        assert proxy.rest_client.details_called
        assert details.name == "Mock Title 720p"
        term_ids = [term.id for term in details.terms]
        assert 12 in term_ids
        # Session not still bound! assert details.terms[0].type.id == 7

        proxy.rest_client.details_called = False
        proxy.details(123123)
        assert proxy.rest_client.details_called == False, 'Proxy not used the cache'


class TestInputPlugin(object):
    config = """
        tasks:
          uncached_db:
            series:
              - Mickey vs Donald
            t411:
              category: cartoons
              terms:
                - Antivirus
            t411_lookup: fill
    """

    @mock.patch('flexget.plugins.api_t411.T411Proxy.set_credential')
    @mock.patch('flexget.plugins.api_t411.T411RestClient.search')
    @mock.patch('flexget.plugins.api_t411.T411RestClient.retrieve_terms_tree')
    @mock.patch('flexget.plugins.api_t411.T411RestClient.retrieve_category_tree')
    @mock.patch('flexget.plugins.api_t411.T411RestClient.details')
    def test_schema(self, mock_details, mock_cat, mock_term, mock_search, mock_auth, execute_task):
        mock_details.return_value = MockRestClient.details_result
        mock_cat.return_value = MockRestClient.cat_result
        mock_term.return_value = MockRestClient.term_result
        mock_search.return_value = MockRestClient.search_result
        mock_auth.return_value = None
        task = execute_task('uncached_db')
        log.debug(task.all_entries)
        assert len(task.all_entries) == 1
        entry = task.all_entries[0]
        quality = entry.get('quality')
        assert quality is not None
        log.debug(quality)
        quality_tester = Requirements('1080p hdtv 10bit dd5.1')
        assert quality_tester.allows(quality)
