from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify, request
from sqlalchemy.orm.exc import NoResultFound

from flexget.plugins.list.pending_list import (
    get_pending_lists, get_list_by_exact_name, PendingListList, get_list_by_id, delete_list_by_id,
    get_entries_by_list_id, get_entry_by_title, PendingListEntry, get_entry_by_id
)
from flexget.api import api, APIResource
from flexget.api.app import (
    NotFoundError, base_message_schema, success_response, etag, pagination_headers, Conflict, BadRequest
)

log = logging.getLogger('pending_list')

pending_list_api = api.namespace('pending_list', description='Pending List operations')


class ObjectsContainer(object):
    pending_list_base_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'added_on': {'type': 'string'}
        }
    }
    pending_list_input_object = copy.deepcopy(pending_list_base_object)
    del pending_list_input_object['properties']['id']
    del pending_list_input_object['properties']['added_on']

    pending_list_return_lists = {'type': 'array', 'items': pending_list_base_object}

    base_entry_object = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'original_url': {'type': 'string'},
            'approved': {'type': 'boolean'}
        },
        'required': ['title', 'original_url'],
        'additionalProperties': True
    }

    pending_list_entry_base_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'added_on': {'type': 'string'},
            'title': {'type': 'string'},
            'original_url': {'type': 'string'},
            'approved': {'type': 'boolean'},
            'entry': base_entry_object
        }
    }

    operation_object = {
        'type': 'object',
        'properties': {
            'operation': {'type': 'string', 'enum': ['approve', 'reject']}
        },
        'required': ['operation'],
        'additionalProperties': False
    }

    pending_lists_entries_return_object = {'type': 'array', 'items': pending_list_entry_base_object}


pending_list_object_schema = api.schema_model('pending_list.return_list', ObjectsContainer.pending_list_base_object)
pending_list_input_object_schema = api.schema_model('pending_list.input_list',
                                                    ObjectsContainer.pending_list_input_object)
pending_list_return_lists_schema = api.schema_model('pending_list.return_lists',
                                                    ObjectsContainer.pending_list_return_lists)
pending_list_operation_schema = api.schema_model('pending_list.operation_schema', ObjectsContainer.operation_object)

list_parser = api.parser()
list_parser.add_argument('name', help='Filter results by list name')


@pending_list_api.route('/')
class PendingListListsAPI(APIResource):
    @etag
    @api.doc(parser=list_parser)
    @api.response(200, 'Successfully retrieved pending lists', pending_list_return_lists_schema)
    def get(self, session=None):
        """ Get pending lists """
        args = list_parser.parse_args()
        name = args.get('name')

        pending_lists = [pending_list.to_dict() for pending_list in get_pending_lists(name=name, session=session)]
        return jsonify(pending_lists)

    @api.validate(pending_list_input_object_schema)
    @api.response(201, model=pending_list_object_schema)
    @api.response(Conflict)
    def post(self, session=None):
        """ Create a new pending list """
        data = request.json
        name = data.get('name')

        try:
            get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            pass
        else:
            raise Conflict('list with name \'%s\' already exists' % name)

        pending_list = PendingListList()
        pending_list.name = name
        session.add(pending_list)
        session.commit()
        resp = jsonify(pending_list.to_dict())
        resp.status_code = 201
        return resp


@pending_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class PendingListListAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=pending_list_object_schema)
    def get(self, list_id, session=None):
        """ Get pending list by ID """
        try:
            list = get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        return jsonify(list.to_dict())

    @api.response(200, description='list successfully deleted', model=base_message_schema)
    @api.response(NotFoundError)
    def delete(self, list_id, session=None):
        """ Delete pending list by ID """
        try:
            delete_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        return success_response('list successfully deleted')


base_entry_schema = api.schema_model('base_entry_schema', ObjectsContainer.base_entry_object)
pending_list_entry_base_schema = api.schema_model('pending_list.entry_base_schema',
                                                  ObjectsContainer.pending_list_entry_base_object)
pending_lists_entries_return_schema = api.schema_model('pending_list.entry_return_schema',
                                                       ObjectsContainer.pending_lists_entries_return_object)

sort_choices = ('id', 'added', 'title', 'original_url', 'list_id', 'approved')
entries_parser = api.pagination_parser(sort_choices=sort_choices, default='title')


@pending_list_api.route('/<int:list_id>/entries/')
@api.doc(params={'list_id': 'ID of the list'}, parser=entries_parser)
@api.response(NotFoundError)
class PendingListEntriesAPI(APIResource):
    @etag
    @api.response(200, model=pending_lists_entries_return_schema)
    def get(self, list_id, session=None):
        """ Get entries by list ID """
        try:
            list = get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)

        args = entries_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page
        descending = sort_order == 'desc'

        kwargs = {
            'start': start,
            'stop': stop,
            'list_id': list_id,
            'order_by': sort_by,
            'descending': descending,
            'session': session
        }

        total_items = list.entries.count()

        if not total_items:
            return jsonify([])

        log.debug('pending lists entries count is %d', total_items)
        entries = [entry.to_dict() for entry in get_entries_by_list_id(**kwargs)]

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(len(entries), per_page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Create response
        rsp = jsonify(entries)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp

    @api.validate(base_entry_schema)
    @api.response(201, description='Successfully created entry object', model=pending_list_entry_base_schema)
    @api.response(Conflict)
    def post(self, list_id, session=None):
        """ Create a new entry object"""
        try:
            get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        data = request.json
        title = data.get('title')
        entry_object = get_entry_by_title(list_id=list_id, title=title, session=session)
        if entry_object:
            raise Conflict('entry with title \'%s\' already exists' % title)
        entry_object = PendingListEntry(entry=data, pending_list_id=list_id)
        if data.get('approved'):
            entry_object.approved = data['approved']
        session.add(entry_object)
        session.commit()
        response = jsonify(entry_object.to_dict())
        response.status_code = 201
        return response


@pending_list_api.route('/<int:list_id>/entries/<int:entry_id>/')
@api.doc(params={'list_id': 'ID of the list', 'entry_id': 'ID of the entry'})
@api.response(NotFoundError)
class PendingListEntryAPI(APIResource):
    @etag
    @api.response(200, model=pending_list_entry_base_schema)
    def get(self, list_id, entry_id, session=None):
        """ Get an entry by list ID and entry ID """
        try:
            entry = get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))

        return jsonify(entry.to_dict())

    @api.response(200, model=base_message_schema)
    def delete(self, list_id, entry_id, session=None):
        """ Delete an entry by list ID and entry ID """
        try:
            entry = get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))
        log.debug('deleting movie %d', entry.id)
        session.delete(entry)
        return success_response('successfully deleted entry %d' % entry.id)

    @api.response(201, model=pending_list_entry_base_schema)
    @api.validate(model=pending_list_operation_schema)
    @api.doc(description='Approve or reject an entry\'s status')
    def put(self, list_id, entry_id, session=None):
        """Sets entry object's pending status"""
        try:
            entry = get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))
        data = request.json
        approved = data['operation'] == 'approve'
        operation_text = 'approved' if approved else 'pending'
        if entry.approved is approved:
            raise BadRequest('Entry with id {} is already {}'.format(entry_id, operation_text))

        entry.approved = approved
        session.commit()
        rsp = jsonify(entry.to_dict())
        rsp.status_code = 201
        return rsp
