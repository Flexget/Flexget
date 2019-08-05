from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from math import ceil

from flask import jsonify, request
from flask_restplus import inputs
from flexget.api import api, APIResource
from flexget.api.app import (
    base_message_schema,
    success_response,
    NotFoundError,
    etag,
    pagination_headers,
    BadRequest,
)
from sqlalchemy.orm.exc import NoResultFound

from . import db

pending_api = api.namespace('pending', description='View and manage pending entries')


class ObjectsContainer(object):
    pending_entry_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'task_name': {'type': 'string'},
            'title': {'type': 'string'},
            'url': {'type': 'string'},
            'approved': {'type': 'boolean'},
            'added': {'type': 'string', 'format': 'date-time'},
        },
    }

    pending_entry_list = {'type': 'array', 'items': pending_entry_object}

    operation_object = {
        'type': 'object',
        'properties': {'operation': {'type': 'string', 'enum': ['approve', 'reject']}},
        'required': ['operation'],
        'additionalProperties': False,
    }


pending_entry_schema = api.schema_model('pending.entry', ObjectsContainer.pending_entry_object)
pending_entry_list_schema = api.schema_model(
    'pending.entry_list', ObjectsContainer.pending_entry_list
)
operation_schema = api.schema_model('pending.operation', ObjectsContainer.operation_object)

filter_parser = api.parser()
filter_parser.add_argument('task_name', help='Filter by task name')
filter_parser.add_argument('approved', type=inputs.boolean, help='Filter by approval status')

sort_choices = ('added', 'task_name', 'title', 'url', 'approved')
pending_parser = api.pagination_parser(parser=filter_parser, sort_choices=sort_choices)

just_task_parser = filter_parser.copy()
just_task_parser.remove_argument('approved')

description = 'Either \'approve\' or \'reject\''


@pending_api.route('/')
class PendingEntriesAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=pending_entry_list_schema)
    @api.doc(parser=pending_parser)
    def get(self, session=None):
        """List all pending entries"""
        args = pending_parser.parse_args()

        # Filter params
        task_name = args.get('task_name')
        approved = args.get('approved')

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'task_name': task_name,
            'approved': approved,
            'start': start,
            'stop': stop,
            'descending': descending,
            'sort_by': sort_by,
            'session': session,
        }

        total_items = session.query(db.PendingEntry).count()

        if not total_items:
            return jsonify([])

        pending_entries = [pending.to_dict() for pending in db.list_pending_entries(**kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(pending_entries))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(pending_entries)

        # Add link header to response
        rsp.headers.extend(pagination)

        return rsp

    @api.validate(operation_schema, description=description)
    @api.response(201, model=pending_entry_list_schema)
    @api.response(204, 'No entries modified')
    @api.doc(parser=just_task_parser)
    def put(self, session=None):
        """Approve/Reject the status of pending entries"""
        args = filter_parser.parse_args()

        data = request.json
        approved = data['operation'] == 'approve'
        task_name = args.get('task_name')

        pending_entries = []
        for entry in db.list_pending_entries(session, task_name=task_name):
            if entry.approved is not approved:
                entry.approved = approved
                pending_entries.append(entry.to_dict())

        rsp = jsonify(pending_entries)
        rsp.status_code = 201 if pending_entries else 204
        return rsp

    @api.response(200, model=base_message_schema)
    @api.doc(parser=filter_parser)
    def delete(self, session=None):
        """Delete pending entries"""
        args = filter_parser.parse_args()

        # Filter params
        task_name = args.get('task_name')
        approved = args.get('approved')

        deleted = session.query(db.PendingEntry)
        if task_name:
            deleted = deleted.filter(db.PendingEntry.task_name == task_name)
        if approved:
            deleted = deleted.filter(db.PendingEntry.approved == approved)
        deleted = deleted.delete()

        return success_response('deleted %s pending entries'.format(deleted))


@pending_api.route('/<int:entry_id>/')
@api.doc(params={'entry_id': 'ID of the entry'})
@api.response(NotFoundError)
class PendingEntryAPI(APIResource):
    @etag
    @api.response(200, model=pending_entry_schema)
    def get(self, entry_id, session=None):
        """Get a pending entry by ID"""
        try:
            entry = db.get_entry_by_id(session, entry_id)
        except NoResultFound:
            raise NotFoundError('No pending entry with ID %s' % entry_id)
        return jsonify(entry.to_dict())

    @api.response(201, model=pending_entry_schema)
    @api.response(BadRequest)
    @api.validate(operation_schema, description=description)
    def put(self, entry_id, session=None):
        """Approve/Reject the status of a pending entry"""
        try:
            entry = db.get_entry_by_id(session, entry_id)
        except NoResultFound:
            raise NotFoundError('No pending entry with ID %s' % entry_id)

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

    @api.response(200, model=base_message_schema)
    def delete(self, entry_id, session=None):
        """Delete a pending entry"""
        try:
            entry = db.get_entry_by_id(session, entry_id)
        except NoResultFound:
            raise NotFoundError('No pending entry with ID %s' % entry_id)
        session.delete(entry)
        return success_response('successfully deleted entry with ID %s' % entry_id)
