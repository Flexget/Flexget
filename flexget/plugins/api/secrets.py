from __future__ import unicode_literals, division, absolute_import

import codecs
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import os

import yaml
from flask import request

from flexget.api import api, APIResource, NotFoundError

log = logging.getLogger('secrets')

secrets_api = api.namespace('secrets', description='View and edit secret file(s)')
empty_object = api.schema('empty_object', {'type': 'object'})


@secrets_api.route('/')
class SecretsAPI(APIResource):
    @api.response(200)
    @api.response(NotFoundError)
    def get(self, session=None):
        secret_file = self.manager.user_config.get('secrets', {})
        if not secret_file:
            raise NotFoundError('No secret file defined in configuration')
        secret_file_path = os.path.join(self.manager.config_base, secret_file)
        with codecs.open(secret_file_path, 'rb', 'utf-8') as f:
            secrets = yaml.load(f)
            return secrets

    @api.response(201, 'Successfully updated secrets file')
    @api.response(NotFoundError)
    @api.validate(empty_object)
    def put(self, session=None):
        data = request.json
        secret_file = self.manager.user_config.get('secrets', {})
        if not secret_file:
            raise NotFoundError('No secret file defined in configuration')
        secret_file_path = os.path.join(self.manager.config_base, secret_file)
        with codecs.open(secret_file_path, 'w', 'utf-8') as f:
            f.write(yaml.safe_dump(data, default_flow_style=False).decode('utf-8'))
            return data, 201
