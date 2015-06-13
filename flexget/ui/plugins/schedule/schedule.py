from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime, timedelta
import threading

from sqlalchemy import Column, Integer, Unicode
from flask import request, render_template, flash, Blueprint, redirect, url_for

from flexget.ui import register_plugin, manager
from flexget.manager import Base
from flexget.event import event, fire_event

log = logging.getLogger('ui.schedule')
schedule = Blueprint('schedule', __name__)


@schedule.route('/', methods=['POST', 'GET'])
def index():
    return render_template('schedule/schedule.html')


register_plugin(schedule, menu='Schedule')
