import logging
from flexget.webui import register_plugin
from flask import request, render_template, flash, Module

log = logging.getLogger('ui.schedule')
schedule = Module(__name__)


@schedule.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        log.info('new interval: %s' % request.form['interval'])
        flash('Updated interval')
    return render_template('schedule.html')


register_plugin(schedule, menu='Schedule')
