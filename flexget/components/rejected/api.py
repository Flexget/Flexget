from math import ceil

from flask import jsonify, request
from loguru import logger
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import APIResource, api
from flexget.api.app import (
    NotFoundError,
    base_message_schema,
    etag,
    pagination_headers,
    success_response,
)

from . import db

logger = logger.bind(name='rejected')

rejected_api = api.namespace('rejected', description='View and manage remembered rejected entries')


def rejected_entry_to_dict(entry):
    return {
        'id': entry.id,
        'added': entry.added,
        'expires': entry.expires,
        'title': entry.title,
        'url': entry.url,
        'rejected_by': entry.rejected_by,
        'reason': entry.reason,
    }


class ObjectsContainer:
    rejected_entry_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'title': {'type': 'string'},
            'url': {'type': 'string'},
            'added': {'type': 'string', 'format': 'date-time'},
            'reason': {'type': 'string'},
            'expires': {'type': 'string', 'format': 'date-time'},
            'rejected_by': {'type': 'string'},
        },
        'required': ['id', 'title', 'url', 'added', 'reason', 'expires', 'rejected_by'],
        'additionalProperties': False,
    }
    rejected_entries_list_object = {'type': 'array', 'items': rejected_entry_object}


rejected_entry_schema = api.schema_model(
    'rejected_failed_entry_schema', ObjectsContainer.rejected_entry_object
)
rejected_entries_list_schema = api.schema_model(
    'rejected_entries_list_schema', ObjectsContainer.rejected_entries_list_object
)

sort_choices = ('added', 'id', 'title', 'url', 'expires', 'rejected_by', 'reason')
rejected_parser = api.pagination_parser(sort_choices=sort_choices)


@rejected_api.route('/')
class Rejected(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=rejected_entries_list_schema)
    @api.doc(parser=rejected_parser)
    def get(self, session=None):
        """List all rejected entries"""
        args = rejected_parser.parse_args()

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
            'start': start,
            'stop': stop,
            'descending': descending,
            'sort_by': sort_by,
            'session': session,
        }

        total_items = db.get_rejected(session, count=True)

        if not total_items:
            return jsonify([])

        failed_entries = [rejected_entry_to_dict(reject) for reject in db.get_rejected(**kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(failed_entries))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(failed_entries)

        # Add link header to response
        rsp.headers.extend(pagination)

        return rsp

    @api.response(200, model=base_message_schema)
    def delete(self, session=None):
        """Clears all rejected entries"""
        entries = session.query(db.RememberEntry).delete()
        if entries:
            session.commit()
            self.manager.config_changed()
        return success_response('successfully deleted %i rejected entries' % entries)


@rejected_api.route('/<int:rejected_entry_id>/')
@api.response(NotFoundError)
class RejectedEntry(APIResource):
    @etag
    @api.response(200, model=rejected_entry_schema)
    def get(self, rejected_entry_id, session=None):
        """Returns a rejected entry"""
        try:
            entry = (
                session.query(db.RememberEntry)
                .filter(db.RememberEntry.id == rejected_entry_id)
                .one()
            )
        except NoResultFound:
            raise NotFoundError('rejected entry ID %d not found' % rejected_entry_id)
        return jsonify(rejected_entry_to_dict(entry))

    @api.response(200, model=base_message_schema)
    def delete(self, rejected_entry_id, session=None):
        """Deletes a rejected entry"""
        try:
            entry = (
                session.query(db.RememberEntry)
                .filter(db.RememberEntry.id == rejected_entry_id)
                .one()
            )
        except NoResultFound:
            raise NotFoundError('rejected entry ID %d not found' % rejected_entry_id)
        session.delete(entry)
        return success_response('successfully deleted rejected entry %i' % rejected_entry_id)
