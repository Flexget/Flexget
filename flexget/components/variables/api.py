from __future__ import unicode_literals, division, absolute_import

import logging

from flask import request, jsonify

from flexget.api import api, APIResource
from flexget.api.app import empty_response, etag
from flexget.components.variables.variables import variables_from_db, variables_to_db

log = logging.getLogger('variables')

variables_api = api.namespace('variables', description='View and edit config variables')


@variables_api.route('/')
class VariablesAPI(APIResource):
    @etag
    @api.response(200, model=empty_response)
    def get(self, session=None):
        """ Get variables data from DB """
        return jsonify(variables_from_db())

    @api.response(201, 'Successfully updated variables file')
    @api.validate(empty_response)
    @api.doc(
        description='Note that editing variables may not be persistent, depending on user config'
    )
    def put(self, session=None):
        """ Store variables data to DB """
        data = request.json
        variables_to_db(data)
        # This will trigger reloading the variables file
        self.manager.validate_config()
        rsp = jsonify(variables_from_db())
        rsp.status_code = 201
        return rsp
