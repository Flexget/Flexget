from __future__ import unicode_literals, division, absolute_import

from flask import Blueprint, jsonify, request
from jsonschema import RefResolutionError

from flexget.config_schema import resolve_ref
from flexget.ui.webui import register_plugin

schema = Blueprint('schema', __name__)


@schema.route('/', defaults={'path': ''})
@schema.route('/<path:path>')
def get_schema(path):
    refpath = '/schema/' + path
    if request.query_string:
        refpath += '?' + request.query_string
    try:
        return jsonify(resolve_ref(refpath))
    except RefResolutionError:
        return 'Schema not found', 404


register_plugin(schema)
