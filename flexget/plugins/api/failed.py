from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, base_message_schema, success_response, NotFoundError
from flexget.plugins.filter.retry_failed import FailedEntry

log = logging.getLogger('failed_api')

retry_failed_api = api.namespace('failed', description='View and manage failed entries')


class ObjectsContainer(object):
    retry_failed_entry_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'title': {'type': 'string'},
            'url': {'type': 'string'},
            'added_at': {'type': 'string', 'format': 'date-time'},
            'reason': {'type': 'string'},
            'count': {'type': 'integer'},
            'retry_time': {'type': 'string', 'format': 'date-time'}
        }
    }
    retry_entries_list_object = {'type': 'array', 'items': retry_failed_entry_object}


retry_failed_entry_schema = api.schema('retry_failed_entry_schema', ObjectsContainer.retry_failed_entry_object)
retry_entries_list_schema = api.schema('retry_entries_list_schema', ObjectsContainer.retry_entries_list_object)


@retry_failed_api.route('/')
class RetryFailed(APIResource):
    @api.response(200, model=retry_entries_list_schema)
    def get(self, session=None):
        """ List all failed entries """
        failed_entries = [failed.to_dict() for failed in session.query(FailedEntry).all()]
        return jsonify(failed_entries)

    @api.response(200, 'successfully deleted failed entry', model=base_message_schema)
    def delete(self, session=None):
        """ Clear all failed entries """
        log.debug('deleting all failed entries')
        deleted = session.query(FailedEntry).delete()
        return success_response('successfully deleted %d failed entries' % deleted)


@retry_failed_api.route('/<int:failed_entry_id>/')
@api.response(NotFoundError)
class RetryFailedID(APIResource):
    @api.doc(params={'failed_entry_id': 'ID of the failed entry'})
    @api.response(200, model=retry_failed_entry_schema)
    def get(self, failed_entry_id, session=None):
        """ Get failed entry by ID """
        try:
            failed_entry = session.query(FailedEntry).filter(FailedEntry.id == failed_entry_id).one()
        except NoResultFound:
            raise NotFoundError('could not find entry with ID %i' % failed_entry_id)
        return jsonify(failed_entry.to_dict())

    @api.response(200, 'successfully delete failed entry', model=base_message_schema)
    def delete(self, failed_entry_id, session=None):
        """ Delete failed entry by ID """
        try:
            failed_entry = session.query(FailedEntry).filter(FailedEntry.id == failed_entry_id).one()
        except NoResultFound:
            raise NotFoundError('could not find entry with ID %i' % failed_entry_id)
        log.debug('deleting failed entry: "%s"' % failed_entry.title)
        session.delete(failed_entry)
        return success_response('successfully delete failed entry %d' % failed_entry_id)
