from __future__ import unicode_literals, division, absolute_import

from flask import jsonify, request

from flexget import plugin
from flexget.api import api, APIResource
from flexget.entry import Entry


list_api = api.namespace('list', description='Manage list plugins')

list_config_schema = {
    'allOf': [
        {'$ref': '/schema/plugins?group=list'},
        {'maxProperties': 1, 'minProperties': 1}
    ]}

# TODO: put this in entry.py?
entry_schema = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'}
    },
    'required': ['title', 'url'],
    'additionalProperties': True
}

list_model ={
    'type': 'object',
    'properties': {
        'config': list_config_schema,
        'item': entry_schema
    },
    'required': ['config', 'item'],
    'additionalProperties': False
}

list_model = api.model('list_model', list_model)

@list_api.route('/items/')
@api.doc(description='Get, delete or create list entries')
class ListAPI(APIResource):
    def get(self, session):
        data = request.json
        for plugin_name, plugin_config in data['config'].iteritems():
            thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
            return jsonify(thelist)

    @api.validate(list_model)
    def post(self, session):
        data = request.json
        for plugin_name, plugin_config in data['config'].iteritems():
            thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
            thelist.add(Entry(data['item']))

    @api.validate(list_model)
    def delete(self, session):
        data = request.json
        for plugin_name, plugin_config in data['config'].iteritems():
            thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
            thelist.discard(Entry(data['item']))
