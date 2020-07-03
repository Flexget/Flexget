from flask import jsonify, request
from loguru import logger

from flexget.api import APIResource, api
from flexget.api.app import empty_response, etag
from flexget.components.variables.variables import variables_from_db, variables_to_db

logger = logger.bind(name='variables')

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

    @api.response(200, 'Successfully updated variables file')
    @api.validate(empty_response)
    @api.doc(
        description='Note that editing variables may not be persistent, depending on user config'
    )
    def patch(self, session=None):
        """ Update variables data to DB """
        data = request.json
        existing_variables = variables_from_db()
        existing_variables.update(data)
        variables_to_db(existing_variables)
        # This will trigger reloading the variables file
        self.manager.validate_config()
        return jsonify(variables_from_db())
