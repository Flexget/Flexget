from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify
from flask import request
from sqlalchemy.orm.exc import NoResultFound
from flexget.plugins.filter.series import FilterSeriesBase
from flexget.api import api, APIResource
from flexget.plugins.list import movie_list as ml
from flexget.utils.tools import split_title_year

SUPPORTED_IDS = FilterSeriesBase().supported_ids
SETTINGS_SCHEMA = FilterSeriesBase().settings_schema
SERIES_ATTRIBUTES = SETTINGS_SCHEMA['properties']

log = logging.getLogger('series_list_api')

series_list_api = api.namespace('series_list', description='Series List operations')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}
empty_response = api.schema('empty', {'type': 'object'})
