from __future__ import unicode_literals, division, absolute_import

import datetime
from math import ceil

from flask import jsonify
from flask import request
from flask_restplus import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource
from flexget.plugins.filter import series

user_api = api.namespace('user', description='Manage user login credentials')

