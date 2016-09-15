from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.api import flask_app
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.webserver import get_secret, register_app

log = logging.getLogger('daemon_api')
api_config_schema = {
    'type': 'boolean',
    'additionalProperties': False
}


@event('config.register')
def register_config():
    register_config_key('api', api_config_schema)


@event('manager.daemon.started')
def register_api(mgr):
    flask_app.secret_key = get_secret()

    if mgr.config.get('api'):
        log.debug('API config detected initiating API')
        register_app('/api', flask_app)
