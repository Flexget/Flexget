import logging
from flexget.ui.webui import register_plugin, db_session
from flask import request, render_template, flash, Module
from flexget.plugin import PluginDependencyError

try:
    from flexget.plugins.plugin_archive import ArchiveEntry
except ImportError:
    raise PluginDependencyError('Requires archive plugin', 'archive')

log = logging.getLogger('ui.archive')
archive = Module(__name__)


@archive.route('/', methods=['POST', 'GET'])
def index():
    context = {}
    if request.method == 'POST':
        pass
    return render_template('archive/archive.html', **context)


@archive.route('/count')
def count():
    return str(db_session.query(ArchiveEntry).count())


@archive.route('/inject')
def inject():
    raise Exception('Not implemented')


register_plugin(archive, menu='Archive')
