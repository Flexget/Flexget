from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.event import event
from flexget.config_schema import register_config_key
from flexget.ui import register_web_ui

log = logging.getLogger("webui")

webui_config_schema = {
    'type': 'boolean'
}


@event('config.register')
def register_config():
    register_config_key('webui', webui_config_schema)


@event('manager.daemon.started')
def register_webui(manager):
    webui_config = manager.config.get('webui')

    if not webui_config:
        log.info("Not starting webui as it's disabled or not set in the config")
    else:
        register_web_ui(manager)
