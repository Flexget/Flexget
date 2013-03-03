from __future__ import unicode_literals, division, absolute_import

from flask import Module, jsonify, request

from flexget.config_schema import resolve_local
from flexget.ui.webui import register_plugin

schema = Module(__name__)


@schema.route('/', defaults={'path': ''})
@schema.route('/<path:path>')
def get_schema(path):
    refpath = '/schema/' + path
    if request.query_string:
        refpath += '?' + request.query_string
    return jsonify(resolve_local(refpath))


register_plugin(schema)