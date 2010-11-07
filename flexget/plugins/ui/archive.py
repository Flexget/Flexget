import logging
from flexget.webui import register_plugin, db_session
from flask import request, render_template, flash, Module

from flexget.plugins.plugin_archive import ArchiveEntry

log = logging.getLogger('ui.archive')
schedule = Module(__name__)


@schedule.route('/', methods=['POST', 'GET'])
def index():

    context = {
        'count': db_session.query(ArchiveEntry).count()}

    if request.method == 'POST':
        pass
    return render_template('archive.html', **context)


register_plugin(schedule, menu='Archive')
