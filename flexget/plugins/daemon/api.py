from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.api import app
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.webserver import get_secret, register_app

api_config_schema = {
    'type': 'boolean',
    'additionalProperties': False
}


@event('config.register')
def register_config():
    register_config_key('api', api_config_schema)


@event('manager.daemon.started')
def register_api(mgr):
    app.secret_key = get_secret()

    if mgr.config.get('api'):
        register_app('/api', app)
