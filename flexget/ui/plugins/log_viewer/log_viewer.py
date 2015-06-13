from __future__ import unicode_literals, division, absolute_import
import logging
from flask import render_template, Blueprint, jsonify, request
from sqlalchemy import Column, DateTime, Integer, Unicode, String, asc, desc, or_, and_
from flexget.ui import register_plugin

log_viewer = Blueprint('log_viewier', __name__, url_prefix='/log')


@log_viewer.route('/')
def index():
    return render_template('log_viewer/log.html')

register_plugin(log_viewer, menu='Log', order=256)