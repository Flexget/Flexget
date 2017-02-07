from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import copy

from flask import request

from flexget import plugin
from flexget.api import api, APIResource
from flexget.api.app import BadRequest, success_response, base_message_schema
from flexget.entry import Entry

lists_api = api.namespace('lists', description='Manage list interface plugins')


class ObjectsContainer(object):
    base_entry_object = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'url': {'type': 'string'}
        },
        'required': ['title', 'url'],
        'additionalProperties': {'type': 'object'}
    }

    list_of_entries = {
        'type': 'array',
        'items': base_entry_object
    }

    single_list = {
        'allOf': [
            {'$ref': '/schema/plugins?interface=list'},
            {'maxProperties': 1,
             'minProperties': 1
             }
        ]}

    list_of_lists = {
        'type': 'array',
        'items': single_list,
        'minProperties': 1
    }

    action_payload = {
        'type': 'object',
        'properties': {
            'lists': list_of_lists,
            'entries': list_of_entries
        },
        'required': ['lists', 'entries'],
        'additionalProperties': False
    }

    clear_payload = copy.deepcopy(action_payload)
    clear_payload['required'] = ['lists']
    del clear_payload['properties']['entries']


action_schema = api.schema('lists.action_payload', ObjectsContainer.action_payload)
clear_schema = api.schema('lists.clear_payload', ObjectsContainer.clear_payload)


@lists_api.route('/add/')
class ListsAPI(APIResource):
    @api.validate(action_schema)
    @api.response(200, 'successfully added entries to list', model=base_message_schema)
    @api.response(BadRequest)
    def post(self, session):
        """Add entries to a list"""
        data = request.json
        lists = data['lists']
        entries = [Entry(entry) for entry in data['entries']]
        for item in lists:
            for plugin_name, plugin_config in item.items():
                try:
                    the_list = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise BadRequest('Plugin {} does not support list interface'.format(plugin_name))
                if the_list.immutable:
                    raise BadRequest('List {} - {} is immutable'.format(plugin_name, plugin_config))
                the_list |= entries
                return success_response('successfully added entries to list {} - {}'.format(plugin_name, plugin_config))


@lists_api.route('/remove/')
class ListsAPI(APIResource):
    @api.validate(action_schema)
    @api.response(200, 'successfully removed entries from list', model=base_message_schema)
    @api.response(BadRequest)
    def post(self, session):
        """Removed entries from a list"""
        data = request.json
        lists = data['lists']
        entries = [Entry(entry) for entry in data['entries']]
        for item in lists:
            for plugin_name, plugin_config in item.items():
                try:
                    the_list = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise BadRequest('Plugin {} does not support list interface'.format(plugin_name))
                if the_list.immutable:
                    raise BadRequest('List {} - {} is immutable'.format(plugin_name, plugin_config))
                the_list -= entries
                return success_response(
                    'successfully removed entries from list {} - {}'.format(plugin_name, plugin_config))


@lists_api.route('/clear/')
class ListsAPI(APIResource):
    @api.validate(clear_schema)
    @api.response(200, 'successfully cleared entries from a list', model=base_message_schema)
    @api.response(BadRequest)
    def post(self, session):
        """Clear an entire list"""
        data = request.json
        lists = data['lists']
        for item in lists:
            for plugin_name, plugin_config in item.items():
                try:
                    the_list = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise BadRequest('Plugin {} does not support list interface'.format(plugin_name))
                if the_list.immutable:
                    raise BadRequest('List {} - {} is immutable'.format(plugin_name, plugin_config))
                the_list.clear()
                return success_response(
                    'successfully cleared all entries from list {} - {}'.format(plugin_name, plugin_config))
