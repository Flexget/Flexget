from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify
from flask import request
from sqlalchemy.orm.exc import NoResultFound
from flexget.plugins.filter.series import FilterSeriesBase
from flexget.api import api, APIResource
from flexget.plugins.list import series_list as sl
from flexget.utils.tools import split_title_year

SUPPORTED_IDS = FilterSeriesBase().supported_ids
SETTINGS_SCHEMA = FilterSeriesBase().settings_schema
SERIES_ATTRIBUTES = SETTINGS_SCHEMA['properties']

log = logging.getLogger('series_list_api')

series_list_api = api.namespace('series_list', description='Series List operations')


class objects_container(object):
    default_error_schema = {
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'message': {'type': 'string'}
        }
    }

    list_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'added_on': {'type': 'string'},
            'name': {'type': 'string'}
        }
    }

    list_input = copy.deepcopy(list_object)
    del list_input['properties']['id']
    del list_input['properties']['added_on']

    return_lists = {'type': 'array', 'items': list_object}


empty_response = api.schema('empty', {'type': 'object'})
default_error_schema = api.schema('default_error_schema', objects_container.default_error_schema)
return_lists_schema = api.schema('return_lists', objects_container.return_lists)
new_list_schema = api.schema('new_list', objects_container.list_input)
list_object_schema = api.schema('list_object', objects_container.list_object)

series_list_parser = api.parser()
series_list_parser.add_argument('name', help='Filter results by list name')


@series_list_api.route('/')
class SeriesListAPI(APIResource):
    @api.response(200, model=return_lists_schema)
    @api.doc(parser=series_list_parser)
    def get(self, session=None):
        """ Gets series lists """
        args = series_list_parser.parse_args()
        name = args.get('name')
        series_lists = [series_list.to_dict() for series_list in sl.get_series_lists(name=name, session=session)]
        return jsonify(series_lists)

    @api.validate(new_list_schema)
    @api.response(201, model=list_object_schema)
    @api.response(500, description='List already exist', model=default_error_schema)
    def post(self, session=None):
        """ Create a new list """
        data = request.json
        name = data.get('name')
        try:
            series_list = sl.get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            series_list = None
        if series_list:
            return {'status': 'error',
                    'message': "list with name '%s' already exists" % name}, 500
        series_list = sl.SeriesListList(name=name)
        session.add(series_list)
        session.commit()
        resp = jsonify(series_list.to_dict())
        resp.status_code = 201
        return resp
