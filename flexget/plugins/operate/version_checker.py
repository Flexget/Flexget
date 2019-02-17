from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
from datetime import datetime

from sqlalchemy import Column, DateTime

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import get_latest_flexget_version_number, get_current_flexget_version

log = logging.getLogger('version_checker')
Base = db_schema.versioned_base('version_checker', 0)


class LastVersionCheck(Base):
    __tablename__ = 'last_version_check'

    last_check_time = Column(DateTime, primary_key=True)

    def __init__(self):
        self.update()

    def update(self):
        self.last_check_time = datetime.now()


schema = {
    'oneOf': [
        {'type': 'boolean'},
        {'type': 'string', 'enum': ['always', 'by_interval']},
        {
            'type': 'object',
            'properties': {
                'lookup': {'type': 'string', 'enum': ['always', 'by_interval']},
                'check_for_dev_version': {'type': 'boolean'},
                'interval': {'type': 'integer'},
            },
            'additionalProperties': False,
        },
    ]
}


class VersionChecker(object):
    """
    A plugin that checks whether user is running the latest flexget version and place a log warning if not.
    Checks via interval to avoid hammering, default is 1 day.

    Can accept boolean or ['always', 'by_interval'] in config.
    Can also accept object. If check_for_dev_version option is True, version will be checked even if current release
    is dev, otherwise, it will be skipped.
    """

    def prepare_config(self, config):
        if isinstance(config, bool) and config is True:
            config = {'lookup': 'by_interval'}
        elif isinstance(config, basestring):
            config = {'lookup': config}

        config.setdefault('lookup', 'by_interval')
        config.setdefault('interval', 1)
        config.setdefault('check_for_dev_version', False)

        return config

    def on_task_start(self, task, config):
        if not config:
            return

        config = self.prepare_config(config)
        current_version = get_current_flexget_version()

        if config.get('check_for_dev_version') is False and current_version.endswith('dev'):
            log.debug('dev version detected, skipping check')
            return

        always_check = bool(config.get('lookup') == 'always')
        interval = config.get('interval')

        session = Session()
        last_check = session.query(LastVersionCheck).first()
        if not always_check:
            if last_check:
                time_dif = datetime.now() - last_check.last_check_time
                should_poll = time_dif.days > interval
            else:
                should_poll = True

            if not should_poll:
                log.debug('version check interval not met, skipping check')
                return

        latest_version = get_latest_flexget_version_number()
        if not latest_version:
            log.warning('Could not get latest version of flexget')
            return
        elif latest_version != current_version:
            log.warning(
                'You are not running latest Flexget Version. Current is %s and latest is %s',
                current_version,
                latest_version,
            )
        if last_check:
            log.debug('updating last check time')
            last_check.update()
        else:
            last_check = LastVersionCheck()
            log.debug('creating instance of last version check in DB')
            session.add(last_check)


@event('plugin.register')
def register_plugin():
    plugin.register(VersionChecker, 'version_checker', api_ver=2)
