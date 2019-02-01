from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import codecs
import logging
import os
from datetime import datetime

import yaml

from jinja2 import TemplateError
from jinja2.nativetypes import NativeEnvironment

from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import Unicode, DateTime, Integer

from flexget import db_schema
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.utils.database import json_synonym

log = logging.getLogger('variables')

DB_VERSION = 0
Base = db_schema.versioned_base('variables', DB_VERSION)


class Variables(Base):
    __tablename__ = 'variables'

    id = Column(Integer, primary_key=True)
    _variables = Column('variables', Unicode)
    variables = json_synonym('_variables')
    added = Column(DateTime, default=datetime.now)


def variables_from_file(config_base, filename):
    variables_file = os.path.join(config_base, filename)
    if not os.path.exists(variables_file):
        raise PluginError('File %s does not exist!' % variables_file)
    try:
        with codecs.open(variables_file, 'rb', 'utf-8') as f:
            variables_dict = yaml.safe_load(f.read())
    except yaml.YAMLError as e:
        raise PluginError('Invalid variables file: %s' % e)
    return variables_dict or {}


def variables_from_db():
    with Session() as session:
        variables = session.query(Variables).first()
        if variables:
            return variables.variables
        else:
            return {}


def variables_to_db(variables_dict):
    with Session() as session:
        variables = session.query(Variables).first()
        if not variables:
            variables = Variables()
        variables.variables = variables_dict
        session.merge(variables)


@event('manager.before_config_validate')
def process_variables(config, manager):
    """Render all string elements of the config against defined variables."""
    env_params = {
        'block_start_string': '^^disabled^^',
        'block_end_string': '^^disabled^^',
        'variable_start_string': '{?',
        'variable_end_string': '?}'
    }
    if 'variables' not in config or config.get('variables') is False:
        return
    env = NativeEnvironment(**env_params)
    if isinstance(config['variables'], bool):
        log.debug('trying to load variables from DB')
        variables = variables_from_db()
    elif isinstance(config['variables'], dict):
        log.debug('loading variables from config')
        variables = config['variables']
    else:
        log.debug('trying to load variables from file')
        variables = variables_from_file(manager.config_base, config['variables'])
        log.debug('updating DB with variable file contents')
        variables_to_db(variables)
    env.globals = variables
    _process(config, env)
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
    elif isinstance(element, str) and '{?' in element:
        try:
            template = environment.from_string(element)
            return template.render()
        except (TemplateError, TypeError):
            return None


variables_config_schema = {'type': ['string', 'boolean', 'object']}


@event('config.register')
def register_config():
    register_config_key('variables', variables_config_schema)
