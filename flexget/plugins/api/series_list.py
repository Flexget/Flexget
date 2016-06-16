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

    return_lists = {
        'type': 'object',
        'properties': {
            'series_lists': {'type': 'array', 'items': list_object}
        }
    }

    input_series_list_id_object = {
        'type': 'array',
        'items': {
            'type': 'object',
            'minProperties': 1,
            'additionalProperties': True
        }
    }

    return_series_list_id_object = copy.deepcopy(input_series_list_id_object)
    return_series_list_id_object.update(
        {'properties': {
            'id': {'type': 'integer'},
            'added_on': {'type': 'string'},
            'series_id': {'type': 'integer'}
        }})
    input_series_object = FilterSeriesBase().settings_schema
    input_series_object['properties'].update({'title': {'type': 'string'}})
    input_series_object['required'] = ['title']
    input_series_object['additionalProperties'] = True

    edit_series_object = FilterSeriesBase().settings_schema

    edit_global_series_object = FilterSeriesBase().settings_schema
    for attribute in FilterSeriesBase().settings_schema['properties']:
        if attribute.endswith('_regexp'):
            del edit_global_series_object['properties'][attribute]
    del edit_global_series_object['properties']['alternate_name']
    del edit_global_series_object['properties']['date_yearfirst']
    del edit_global_series_object['properties']['date_dayfirst']
    del edit_global_series_object['properties']['identified_by']
    del edit_global_series_object['title']

    return_series_object = copy.deepcopy(input_series_object)
    return_series_object['properties']['series_list_identifiers'] = {'type': 'array',
                                                                     'items': return_series_list_id_object}
    return_series_object['properties'].update({'added_on': {'type': 'string', 'format': 'date-time'}})

    series_array_object = {'type': 'array', 'items': return_series_object}

    return_series_list = {
        'type': 'object',
        'properties': {
            'series': series_array_object,
            'number_of_series': {'type': 'integer'},
            'total_number_of_series': {'type': 'integer'},
            'page_number': {'type': 'integer'}
        }
    }

    return_series_list_edit = {
        'type': 'object',
        'properties': {
            'series': series_array_object
        }
    }


empty_response = api.schema('empty', {'type': 'object'})
default_error_schema = api.schema('default_error_schema', objects_container.default_error_schema)
return_lists_schema = api.schema('return_lists', objects_container.return_lists)
new_list_schema = api.schema('new_list', objects_container.list_input)
list_object_schema = api.schema('list_object', objects_container.list_object)
return_series_list_series_schema = api.schema('return_series', objects_container.return_series_list)
input_series_schema = api.schema('input_series', objects_container.input_series_object)
return_series_schema = api.schema('return_series_list', objects_container.return_series_object)
edit_series_schema = api.schema('edit_series', objects_container.edit_series_object)
edit_global_series_schema = api.schema('edit_series_list', objects_container.edit_global_series_object)
return_series_list_edit_schema = api.schema('return_series_list', objects_container.return_series_list_edit)

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
        series_lists = [series_list.to_dict() for series_list in
                        sl.SeriesListDB.get_series_lists(name=name, session=session)]
        return jsonify({'series_lists': series_lists})

    @api.validate(new_list_schema)
    @api.response(201, model=list_object_schema)
    @api.response(500, description='List already exist', model=default_error_schema)
    def post(self, session=None):
        """ Create a new list """
        data = request.json
        name = data.get('name')
        try:
            series_list = sl.SeriesListDB.get_list_by_exact_name(name=name, session=session)
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


@series_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class SeriesListListAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=list_object_schema)
    def get(self, list_id, session=None):
        """ Get list by ID """
        try:
            series_list = sl.SeriesListDB.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return jsonify(series_list.to_dict())

    @api.response(200, model=empty_response)
    @api.response(404, model=default_error_schema)
    def delete(self, list_id, session=None):
        """ Delete list by ID """
        try:
            series_list = sl.SeriesListDB.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        session.delete(series_list)
        return {}

    @api.response(404, model=default_error_schema)
    @api.response(200, model=return_series_list_edit_schema)
    @api.validate(edit_global_series_schema)
    def put(self, list_id, session=None):
        """ Edit list by ID """
        data = request.json
        updated_series_list = []
        try:
            series_list = sl.SeriesListDB.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        for series in series_list.series:
            updated_series_list.append(sl.SeriesListDB.get_db_series(data, series))
        series_list.series = updated_series_list
        session.commit()
        return jsonify({'series': [series.to_dict() for series in updated_series_list]})


series_parser = api.parser()
series_parser.add_argument('sort_by', choices=('title', 'added'), default='title',
                           help='Sort by attribute')
series_parser.add_argument('order', choices=('desc', 'asc'), default='desc', help='Sorting order')
series_parser.add_argument('page', type=int, default=1, help='Page number')
series_parser.add_argument('page_size', type=int, default=10, help='Number of series per page')

series_identifiers_doc = "Any recognized series identifiers that are part of the payload will be added ot series. Add" \
                         "them to the root of the payload."


@series_list_api.route('/<int:list_id>/series/')
class SeriesListSeriesAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=return_series_list_series_schema)
    @api.doc(params={'list_id': 'ID of the list'}, parser=series_parser)
    def get(self, list_id, session=None):
        """ Get series by list ID """

        args = series_parser.parse_args()
        page = args.get('page')
        page_size = args.get('page_size')

        start = page_size * (page - 1)
        stop = start + page_size
        if args.get('order') == 'desc':
            descending = True
        else:
            descending = False

        kwargs = {
            'start': start,
            'stop': stop,
            'list_id': list_id,
            'order_by': args.get('sort_by'),
            'descending': descending,
            'session': session
        }
        try:
            sl.SeriesListDB.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        count = sl.SeriesListDB.get_series_by_list_id(count=True, **kwargs)
        series = [series.to_dict() for series in sl.SeriesListDB.get_series_by_list_id(**kwargs)]
        pages = int(ceil(count / float(page_size)))

        number_of_series = min(page_size, count)

        return jsonify({'series': series,
                        'number_of_series': number_of_series,
                        'total_number_of_series': count,
                        'page': page,
                        'total_number_of_pages': pages})

    @api.validate(model=input_series_schema, description=series_identifiers_doc)
    @api.response(201, model=return_series_schema)
    @api.response(404, description='List not found', model=default_error_schema)
    @api.response(500, description='Series already exist in list', model=default_error_schema)
    def post(self, list_id, session=None):
        """ Add series to list by ID """
        try:
            series_list = sl.SeriesListDB.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        data = request.json
        title = data.get('title')
        series = sl.SeriesListDB.get_series_by_title(list_id=list_id, title=title, session=session)
        if series:
            return {'status': 'error',
                    'message': 'series with name "%s" already exist in list %d' % (title, list_id)}, 500
        db_series = sl.SeriesListDB.get_db_series(data)
        series_list.series.append(db_series)
        session.commit()
        response = jsonify(db_series.to_dict())
        response.status_code = 201
        return response


@series_list_api.route('/<int:list_id>/series/<int:series_id>/')
@api.doc(params={'list_id': 'ID of the list', 'series_id': 'ID of the series'})
@api.response(404, description='List or series not found', model=default_error_schema)
class SeriesListSeriesAPI(APIResource):
    @api.response(200, model=return_series_schema)
    def get(self, list_id, series_id, session=None):
        """ Get a series by list ID and series ID """
        try:
            series = sl.SeriesListDB.get_series_by_id(list_id=list_id, series_id=series_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find series with id %d in list %d' % (series_id, list_id)}, 404
        return jsonify(series.to_dict())

    @api.response(200, model=empty_response)
    def delete(self, list_id, series_id, session=None):
        """ Delete a series by list ID and series ID """
        try:
            series = sl.SeriesListDB.get_series_by_id(list_id=list_id, series_id=series_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find series with id %d in list %d' % (series_id, list_id)}, 404
        log.debug('deleting series %d', series_id)
        session.delete(series)
        return {}

    @api.validate(model=edit_series_schema, description=series_identifiers_doc)
    @api.response(200, model=return_series_schema)
    @api.doc(description='Sent series data will override any existing data that the series currently holds')
    def put(self, list_id, series_id, session=None):
        """ Edit series data """
        try:
            series = sl.SeriesListDB.get_series_by_id(list_id=list_id, series_id=series_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find series with id %d in list %d' % (series_id, list_id)}, 404
        title = series.title
        data = request.json
        data.update({'title': title})
        series = sl.SeriesListDB.get_db_series(data, series)
        session.commit()
        return jsonify(series.to_dict())
