import logging
from flexget.webui import app, register_menu
from flask import request, render_template, flash

log = logging.getLogger('ui.schedule')


@app.route('/schedule', methods=['POST', 'GET'])
def scheduler():
    if request.method == 'POST':
        log.info('new interval: %s' % request.form['interval'])
        flash('Updated interval')
    return render_template('schedule.html')


register_menu('/schedule', 'Schedule')
