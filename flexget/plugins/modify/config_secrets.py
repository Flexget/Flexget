from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import codecs
import logging
import os
from datetime import datetime

import yaml

from jinja2 import TemplateError

from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import Unicode, DateTime, Integer

from flexget import db_schema
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.utils.database import json_synonym

log = logging.getLogger('secrets')

DB_VERSION = 0
Base = db_schema.versioned_base('secrets', DB_VERSION)


class Secrets(Base):
    __tablename__ = 'secrets'

    id = Column(Integer, primary_key=True)
    _secrets = Column('secrets', Unicode)
    secrets = json_synonym('_secrets')
    added = Column(DateTime, default=datetime.now)


def secrets_from_file(config_base, filename):
    secret_file = os.path.join(config_base, filename)
    if not os.path.exists(secret_file):
        raise PluginError('File %s does not exist!' % secret_file)
    try:
        with codecs.open(secret_file, 'rb', 'utf-8') as f:
            secrets_dict = yaml.safe_load(f.read())
    except yaml.YAMLError as e:
        raise PluginError('Invalid secrets file: %s' % e)
    return secrets_dict or {}


def secrets_from_db():
    with Session() as session:
        secrets = session.query(Secrets).first()
        if secrets:
            return secrets.secrets
        else:
            return {}


def secrets_to_db(secrets_dict):
    with Session() as session:
        secrets = session.query(Secrets).first()
        if not secrets:
            secrets = Secrets()
        secrets.secrets = secrets_dict
        session.merge(secrets)


@event('manager.before_config_validate')
def process_secrets(config, manager):
    """Adds the secrets to the jinja environment globals and attempt to render all string elements of the config."""
    # Environment isn't set up at import time, have to delay the import until here
    from flexget.utils.template import environment
    if 'secrets' not in config or config.get('secrets') is False:
        return
    if isinstance(config['secrets'], bool):
        log.debug('trying to load secrets from DB')
        secrets = secrets_from_db()
    else:
        log.debug('trying to load secrets from file')
        secrets = secrets_from_file(manager.config_base, config['secrets'])
        log.debug('updating DB with secret file contents')
        secrets_to_db(secrets)
    environment.globals['secrets'] = secrets
    _process(config, environment)
    return config


def _process(element, environment):
    if isinstance(element, dict):
        for k, v in element.items():
            new_key = _process(k, environment)
            if new_key:
                element[new_key] = element.pop(k)
                k = new_key
            val = _process(element[k], environment)
            if val:
                element[k] = val
    elif isinstance(element, list):
        for i, v in enumerate(element):
            val = _process(v, environment)
            if val:
                element[i] = val
    elif isinstance(element, basestring) and '{{' in element:
        try:
            template = environment.from_string(element)
            return template.render()
        except (TemplateError, TypeError):
            return None


secrets_config_schema = {'type': ['string', 'boolean']}


@event('config.register')
def register_config():
    register_config_key('secrets', secrets_config_schema)
