from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify, request
from sqlalchemy.orm.exc import NoResultFound

import flexget.plugins.list.entry_list as el
from flexget.api import api, APIResource

log = logging.getLogger('entry_list')

entry_list_api = api.namespace('entry_list', description='Entry List operations')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}
empty_response = api.schema('empty', {'type': 'object'})

default_error_schema = api.schema('default_error_schema', default_error_schema)
entry_list_base_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'name': {'type': 'string'},
        'added_on': {'type': 'string'}
    }
}
entry_list_input_object = copy.deepcopy(entry_list_base_object)
del entry_list_input_object['properties']['id']
del entry_list_input_object['properties']['added_on']

entry_list_return_lists = {'type': 'array', 'items': entry_list_base_object}

entry_list_object_schema = api.schema('entry_list_object_schema', entry_list_base_object)
entry_list_input_object_schema = api.schema('entry_list_input_object_schema', entry_list_input_object)
entry_list_return_lists_schema = api.schema('entry_list_return_lists_schema', entry_list_return_lists)

entry_list_parser = api.parser()
entry_list_parser.add_argument('name', help='Filter results by list name')


@entry_list_api.route('/')
class EntryListListsAPI(APIResource):
    @api.doc(parser=entry_list_parser)
    @api.response(200, 'Successfully retrieved entry lists', entry_list_return_lists_schema)
    def get(self, session=None):
        """ Get entry lists """
        args = entry_list_parser.parse_args()
        name = args.get('name')

        entry_lists = [entry_list.to_dict() for entry_list in el.get_entry_lists(name=name, session=session)]
        return jsonify({'entry_lists': entry_lists})

    @api.validate(entry_list_input_object_schema)
    @api.response(201, model=entry_list_return_lists_schema)
    @api.response(500, description='List already exist', model=default_error_schema)
    def post(self, session=None):
        """ Create a new entry list """
        data = request.json
        name = data.get('name')
        new_list = False
        try:
            entry_list = el.get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            new_list = True
        if not new_list:
            return {'status': 'error',
                    'message': "list with name '%s' already exists" % name}, 500
        entry_list = el.EntryListList(name=name)
        session.add(entry_list)
        session.commit()
        resp = jsonify(entry_list.to_dict())
        resp.status_code = 201
        return resp


@entry_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class EntryListListAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=entry_list_object_schema)
    def get(self, list_id, session=None):
        """ Get list by ID """
        try:
            list = el.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return jsonify(list.to_dict())

    @api.response(200, model=empty_response)
    @api.response(404, model=default_error_schema)
    def delete(self, list_id, session=None):
        """ Delete list by ID """
        try:
            el.delete_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return {}


base_entry_object = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'original_url': {'type': 'string'}
    },
    'required': ['title', 'original_url'],
    'additionalProperties': True
}

entry_list_entry_base_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'name': {'type': 'string'},
        'added_on': {'type': 'string'},
        'title': {'type': 'string'},
        'original_url': {'type': 'string'},
        'entry': base_entry_object,

    }
}

entry_lists_entries_return_object = {
    'type': 'object',
    'properties': {
        'entries': {'type': 'array', 'items': entry_list_entry_base_object},
        'total_number_of_entries': {'type': 'integer'},
        'number_of_entries': {'type': 'integer'},
        'page': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'}
    }
}

base_entry_schema = api.schema('base_entry_schema', base_entry_object)
entry_list_entry_base_schema = api.schema('entry_list_entry_base_schema', entry_list_entry_base_object)
entry_lists_entries_return_schema = api.schema('entry_lists_entries_return_schema', entry_lists_entries_return_object)

entry_list_parser = api.parser()
entry_list_parser.add_argument('sort_by', choices=('id', 'added', 'title', 'original_url', 'list_id'), default='title',
                               help='Sort by attribute')
entry_list_parser.add_argument('order', choices=('desc', 'asc'), default='desc', help='Sorting order')
entry_list_parser.add_argument('page', type=int, default=1, help='Page number')
entry_list_parser.add_argument('page_size', type=int, default=10, help='Number of movies per page')


@entry_list_api.route('/<int:list_id>/entries/')
class EntryListEntriesAPI(APIResource):
    @api.response(404, 'List does not exist', model=default_error_schema)
    @api.response(200, model=entry_lists_entries_return_schema)
    @api.doc(params={'list_id': 'ID of the list'}, parser=entry_list_parser)
    def get(self, list_id, session=None):
        """ Get entries by list ID """

        args = entry_list_parser.parse_args()
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
            list = el.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        count = el.get_entries_by_list_id(count=True, **kwargs)
        log.debug('entry lists entries count is %d', count)
        entries = [entry.to_dict() for entry in el.get_entries_by_list_id(**kwargs)]
        pages = int(ceil(count / float(page_size)))

        number_of_entries = min(page_size, count)

        return jsonify({
            'entries': entries,
            'total_number_of_entries': count,
            'number_of_entries': number_of_entries,
            'page': page,
            'total_number_of_pages': pages
        })

    @api.validate(base_entry_schema)
    @api.response(201, description='Successfully created entry object', model=entry_list_entry_base_schema)
    @api.response(404, 'List id not found', model=default_error_schema)
    @api.response(500, 'Entry already exist', model=default_error_schema)
    def post(self, list_id, session=None):
        """ Create a new entry object"""
        try:
            list = el.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        data = request.json
        title = data.get('title')
        entry_object = el.get_entry_by_title(list_id=list_id, title=title, session=session)
        if entry_object:
            return {'status': 'error',
                    'message': "entry with title '%s' already exists" % title}, 500
        entry_object = el.EntryListEntry(entry=data, entry_list_id=list_id)
        session.add(entry_object)
        session.commit()
        response = jsonify({'entry': entry_object.to_dict()})
        response.status_code = 201
        return response


@entry_list_api.route('/<int:list_id>/entries/<int:entry_id>/')
@api.doc(params={'list_id': 'ID of the list', 'entry_id': 'ID of the entry'})
@api.response(404, description='List or entry not found', model=default_error_schema)
class EntryListEntryAPI(APIResource):
    @api.response(200, model=entry_list_entry_base_schema)
    def get(self, list_id, entry_id, session=None):
        """ Get an entry by list ID and entry ID """
        try:
            entry = el.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find entry with id %d in list %d' % (entry_id, list_id)}, 404
        return jsonify(entry.to_dict())

    @api.response(200, model=empty_response)
    def delete(self, list_id, entry_id, session=None):
        """ Delete an entry by list ID and entry ID """
        try:
            entry = el.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find entry with id %d in list %d' % (entry_id, list_id)}, 404
        log.debug('deleting movie %d', entry.id)
        session.delete(entry)
        return {}

    @api.validate(model=base_entry_schema)
    @api.response(200, model=entry_list_entry_base_schema)
    @api.doc(description='Sent entry data will override any existing entry data the existed before')
    def put(self, list_id, entry_id, session=None):
        """ Sets entry object's entry data """
        try:
            entry = el.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find entry with id %d in list %d' % (entry_id, list_id)}, 4044
        data = request.json
        entry.entry = data
        session.commit()
        return jsonify(entry.to_dict())
