from __future__ import unicode_literals, division, absolute_import

import os
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

import yaml
from flask import jsonify

from flexget.api import api, APIResource, NotFoundError, ApiError

log = logging.getLogger('secrets')

secrets_api = api.namespace('secrets', description='View and edit secret file(s)')


@secrets_api.route('/')
@api.doc(description='Note that changing the secret file may change its structure')
class SecretsAPI(APIResource):
    @api.response(200)
    @api.response(NotFoundError)
    def get(self, session=None):
        secret_file = self.manager.user_config.get('secrets', {})
        if not secret_file:
            raise NotFoundError('No secret file defined in configuration')
        secret_file_path = os.path.join(self.manager.config_base, secret_file)
        with open(secret_file_path, 'r', encoding='utf-8') as f:
            secrets = yaml.load(f)
            return secrets
