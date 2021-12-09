import copy
from math import ceil

from flask import jsonify, request
from loguru import logger
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import APIResource, api
from flexget.api.app import (
    Conflict,
    NotFoundError,
    base_message_schema,
    etag,
    pagination_headers,
    success_response,
)

from . import db

logger = logger.bind(name='entry_list')

entry_list_api = api.namespace('entry_list', description='Entry List operations')


class ObjectsContainer:
    entry_list_base_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'added_on': {'type': 'string'},
        },
    }
    entry_list_input_object = copy.deepcopy(entry_list_base_object)
    del entry_list_input_object['properties']['id']
    del entry_list_input_object['properties']['added_on']

    entry_list_return_lists = {'type': 'array', 'items': entry_list_base_object}

    base_entry_object = {
        'type': 'object',
        'properties': {'title': {'type': 'string'}, 'original_url': {'type': 'string'}},
        'required': ['title', 'original_url'],
        'additionalProperties': True,
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
        },
    }

    entry_lists_entries_return_object = {'type': 'array', 'items': entry_list_entry_base_object}

    batch_ids = {'type': 'array', 'items': {'type': 'integer'}, 'uniqueItems': True, 'minItems': 1}

    batch_remove_object = {
        'type': 'object',
        'properties': {'ids': batch_ids},
        'required': ['ids'],
        'additionalProperties': False,
    }


entry_list_object_schema = api.schema_model(
    'entry_list_object_schema', ObjectsContainer.entry_list_base_object
)
entry_list_input_object_schema = api.schema_model(
    'entry_list_input_object_schema', ObjectsContainer.entry_list_input_object
)
entry_list_return_lists_schema = api.schema_model(
    'entry_list_return_lists_schema', ObjectsContainer.entry_list_return_lists
)
entry_list_batch_remove_schema = api.schema_model(
    'entry_list.batch_remove_object', ObjectsContainer.batch_remove_object
)

entry_list_parser = api.parser()
entry_list_parser.add_argument('name', help='Filter results by list name')


@entry_list_api.route('/')
class EntryListListsAPI(APIResource):
    @etag
    @api.doc(parser=entry_list_parser)
    @api.response(200, 'Successfully retrieved entry lists', entry_list_return_lists_schema)
    def get(self, session=None):
        """Get entry lists"""
        args = entry_list_parser.parse_args()
        name = args.get('name')

        entry_lists = [
            entry_list.to_dict() for entry_list in db.get_entry_lists(name=name, session=session)
        ]
        return jsonify(entry_lists)

    @api.validate(entry_list_input_object_schema)
    @api.response(201, model=entry_list_object_schema)
    @api.response(Conflict)
    def post(self, session=None):
        """Create a new entry list"""
        data = request.json
        name = data.get('name')
        new_list = False
        try:
            db.get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            new_list = True
        if not new_list:
            raise Conflict('list with name \'%s\' already exists' % name)
        entry_list = db.EntryListList(name=name)
        session.add(entry_list)
        session.commit()
        resp = jsonify(entry_list.to_dict())
        resp.status_code = 201
        return resp


@entry_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class EntryListListAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=entry_list_object_schema)
    def get(self, list_id, session=None):
        """Get list by ID"""
        try:
            list = db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        return jsonify(list.to_dict())

    @api.response(200, description='list successfully deleted', model=base_message_schema)
    @api.response(NotFoundError)
    def delete(self, list_id, session=None):
        """Delete list by ID"""
        try:
            db.delete_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        return success_response('list successfully deleted')


base_entry_schema = api.schema_model('base_entry_schema', ObjectsContainer.base_entry_object)
entry_list_entry_base_schema = api.schema_model(
    'entry_list_entry_base_schema', ObjectsContainer.entry_list_entry_base_object
)
entry_lists_entries_return_schema = api.schema_model(
    'entry_lists_entries_return_schema', ObjectsContainer.entry_lists_entries_return_object
)

sort_choices = ('id', 'added', 'title', 'original_url', 'list_id')
entries_parser = api.pagination_parser(sort_choices=sort_choices, default='title')


@entry_list_api.route('/<int:list_id>/entries/')
@api.response(NotFoundError)
class EntryListEntriesAPI(APIResource):
    @etag
    @api.response(200, model=entry_lists_entries_return_schema)
    @api.doc(params={'list_id': 'ID of the list'}, parser=entries_parser)
    def get(self, list_id, session=None):
        """Get entries by list ID"""
        try:
            list = db.get_list_by_id(list_id=list_id, session=session)
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
            'session': session,
        }

        total_items = list.entries.count()

        if not total_items:
            return jsonify([])

        logger.debug('entry lists entries count is {}', total_items)
        entries = [entry.to_dict() for entry in db.get_entries_by_list_id(**kwargs)]

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
    @api.response(
        201, description='Successfully created entry object', model=entry_list_entry_base_schema
    )
    @api.response(Conflict)
    def post(self, list_id, session=None):
        """Create a new entry object"""
        try:
            db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        data = request.json
        title = data.get('title')
        entry_object = db.get_entry_by_title(list_id=list_id, title=title, session=session)
        if entry_object:
            raise Conflict('entry with title \'%s\' already exists' % title)
        entry_object = db.EntryListEntry(entry=data, entry_list_id=list_id)
        session.add(entry_object)
        session.commit()
        response = jsonify(entry_object.to_dict())
        response.status_code = 201
        return response


@entry_list_api.route('/<int:list_id>/entries/<int:entry_id>/')
@api.doc(params={'list_id': 'ID of the list', 'entry_id': 'ID of the entry'})
@api.response(NotFoundError)
class EntryListEntryAPI(APIResource):
    @etag
    @api.response(200, model=entry_list_entry_base_schema)
    def get(self, list_id, entry_id, session=None):
        """Get an entry by list ID and entry ID"""
        try:
            entry = db.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))

        return jsonify(entry.to_dict())

    @api.response(200, model=base_message_schema)
    def delete(self, list_id, entry_id, session=None):
        """Delete an entry by list ID and entry ID"""
        try:
            entry = db.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))
        logger.debug('deleting movie {}', entry.id)
        session.delete(entry)
        return success_response('successfully deleted entry %d' % entry.id)

    @api.validate(model=base_entry_schema)
    @api.response(201, model=entry_list_entry_base_schema)
    @api.doc(
        description='Sent entry data will override any existing entry data the existed before'
    )
    def put(self, list_id, entry_id, session=None):
        """Sets entry object's entry data"""
        try:
            entry = db.get_entry_by_id(list_id=list_id, entry_id=entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find entry with id %d in list %d' % (entry_id, list_id))
        data = request.json
        entry.entry = data
        if data.get('title'):
            entry.title = data['title']
        if data.get('original_url'):
            entry.original_url = data['original_url']
        session.commit()
        resp = jsonify(entry.to_dict())
        resp.status_code = 201
        return resp


@entry_list_api.route('/<int:list_id>/entries/batch')
@api.doc(params={'list_id': 'ID of the list'})
@api.response(NotFoundError)
class EntryListEntriesBatchAPI(APIResource):
    @api.response(204)
    @api.validate(model=entry_list_batch_remove_schema)
    @api.doc(description='Remove multiple entries')
    def delete(self, list_id, session=None):
        """Remove multiple entries"""
        data = request.json
        entry_ids = data.get('ids')
        try:
            entries = db.get_entries_by_list_id(list_id, entry_ids=entry_ids, session=session)
        except NoResultFound:
            raise NotFoundError(f'could not find entries in list {list_id}')

        for entry in entries:
            session.delete(entry)
        session.commit()
        response = jsonify([])
        response.status_code = 204

        return response
