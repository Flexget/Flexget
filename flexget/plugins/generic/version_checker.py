from __future__ import unicode_literals, division, absolute_import

import logging
from datetime import datetime

from sqlalchemy import Column, DateTime

import flexget
from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils import requests

log = logging.getLogger('ver_checker')
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
        {'type': 'object',
         'properties': {
             'lookup': {'type': 'string', 'enum': ['always', 'by_interval']},
             'check_for_dev_version': {'type': 'boolean'},
             'interval': {'type': 'integer'}
         },
         'additionalProperties': False}

    ]
}


def get_latest_flexget_version_number():
    """
    Return latest Flexget version from http://download.flexget.com/latestversion
    """
    try:
        page = requests.get('http://download.flexget.com/latestversion')
    except requests.RequestException:
        log.warning('Error getting latest version number from download.flexget.com')
        return
    ver = page.text.strip()
    return ver


class VersionChecker(object):
    """
    A builtin plugin that checks whether user is running the latest flexget version and place a log warning if not.
    Checks via interval to avoid hammering, default is 1 day.

    Can accept boolean or ['always', 'by_interval'] in config.
    Can also accept object. If check_for_dev_version option is True, version will be checked even if current release
    is dev, otherwise, it will be skipped.
    """

    def prepare_config(self, config):
        if config is False:
            log.debug('Version check is disabled')
            return

        if isinstance(config, basestring) or not config:
            config = {'lookup': config}

        config.setdefault('lookup', 'by_interval')
        config.setdefault('interval', 1)
        config.setdefault('check_for_dev_version', False)

        return config

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        current_version = flexget.__version__

        if config.get('check_for_dev_version') is False and current_version.endswith('dev'):
            log.debug('dev version detected, skipping check')
            return

        always_check = config.get('lookup') == 'always'
        interval = config.get('interval')

        with Session() as session:
            last_check = session.query(LastVersionCheck.last_check_time).first()
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
                return
            elif latest_version != current_version:
                log.warning('You are not running latest Flexget Version. Current is %s and latest is %s',
                            current_version, latest_version)
            if last_check:
                log.debug('updating last check time')
                last_check.update()
            else:
                last_check = LastVersionCheck()
                log.debug('creating instance of last version check in DB')
                session.add(last_check)


@event('plugin.register')
def register_plugin():
    plugin.register(VersionChecker, 'version_checker', builtin=True, api_ver=2)
