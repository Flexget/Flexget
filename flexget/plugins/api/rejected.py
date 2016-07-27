from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, BadRequest
from flexget.plugins.filter.remember_rejected import RememberEntry

log = logging.getLogger('rejected')

rejected_api = api.namespace('rejected', description='View and manage remembered rejected entries')


def rejected_entry_to_dict(entry):
    return {
        'id': entry.id,
        'added': entry.added,
        'expires': entry.expires,
        'title': entry.title,
        'url': entry.url,
        'rejected_by': entry.rejected_by,
        'reason': entry.reason
    }


rejected_entry_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'title': {'type': 'string'},
        'url': {'type': 'string'},
        'added': {'type': 'string', 'format': 'date-time'},
        'reason': {'type': 'string'},
        'expires': {'type': 'string', 'format': 'date-time'},
        'rejected_by': {'type': 'string'}
    }
}
rejected_entries_list_object = {
    'type': 'object',
    'properties': {
        'rejected_entries': {'type': 'array', 'items': rejected_entry_object},
        'number_of_rejected_entries': {'type': 'integer'}
    }
}

rejected_entry_schema = api.schema('rejected_failed_entry_schema', rejected_entry_object)
rejected_entries_list_schema = api.schema('rejected_entries_list_schema', rejected_entries_list_object)


@rejected_api.route('/')
class Rejected(APIResource):
    @api.response(200, model=rejected_entries_list_schema)
    def get(self, session=None):
        """ List all rejected entries """
        entries = session.query(RememberEntry).all()
        return jsonify(rejected_entries=[rejected_entry_to_dict(e) for e in entries],
                       number_of_rejected_entries=len(entries))

    @api.response(200)
    def delete(self, session=None):
        """ Clears all rejected entries"""
        entries = session.query(RememberEntry).delete()
        if entries:
            session.commit()
            self.manager.config_changed()
        return {'status': 'success',
                'message': 'successfully deleted %i rejected entries' % entries}


@rejected_api.route('/<int:rejected_entry_id>/')
class RejectedEntry(APIResource):
    @api.response(200, model=rejected_entry_schema)
    @api.response(BadRequest)
    def get(self, rejected_entry_id, session=None):
        """ Returns a rejected entry """
        try:
            entry = session.query(RememberEntry).filter(RememberEntry.id == rejected_entry_id).one()
        except NoResultFound:
            raise BadRequest('rejected entry ID %d not found' % rejected_entry_id)
        return jsonify(rejected_entry_to_dict(entry))

    def delete(self, rejected_entry_id, session=None):
        """ Deletes a rejected entry """
        try:
            entry = session.query(RememberEntry).filter(RememberEntry.id == rejected_entry_id).one()
        except NoResultFound:
            raise BadRequest('rejected entry ID %d not found' % rejected_entry_id)
        session.delete(entry)
        return {'status': 'success',
                'message': 'successfully deleted rejected entry %i' % rejected_entry_id}
