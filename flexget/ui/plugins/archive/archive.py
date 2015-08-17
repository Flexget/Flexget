from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.ui.webui import db_session, app
from flask import request, render_template, flash, Blueprint
from flexget.plugin import DependencyError

try:
    from flexget.plugins.generic.archive import ArchiveEntry, search
except ImportError:
    raise DependencyError(issued_by='ui.archive', missing='archive')

log = logging.getLogger('ui.archive')
archive = Blueprint('archive', __name__)


# TODO: refactor this filter to some globally usable place (webui.py?)
#       also flexget/plugins/ui/utils.py needs to be removed
#       ... mainly because we have flexget/utils for that :)


@app.template_filter('pretty_age')
def pretty_age_filter(value):
    import time
    from flexget.ui.utils import pretty_date
    return pretty_date(time.mktime(value.timetuple()))


@archive.route('/', methods=['POST', 'GET'])
def index():
    context = {}
    if request.method == 'POST':
        text = request.form.get('keyword', None)
        if text == '':
            flash('Empty search?', 'error')
        elif len(text) < 5:
            flash('Search text is too short, use at least 5 characters', 'error')
        else:
            results = search(db_session, text)
            if not results:
                flash('No results', 'info')
            else:
                # not sure if this len check is a good idea, I think it forces to load all items from db ?
                if len(results) > 500:
                    flash('Too many results, displaying first 500', 'error')
                    results = results[0:500]
                context['results'] = results
    return render_template('archive/archive.html', **context)


@archive.route('/count')
def count():
    log.debug('getting count for archive')
    return str(db_session.query(ArchiveEntry).count())


# TODO: Fix this
@archive.route('/inject/<id>')
def inject(id):
    # TODO: Do it like the cli command does
    options = {'archive_inject_id': id, 'archive_inject_immortal': True}
    executor.execute(options=options)
    flash('Queued execution, see log for results', 'info')
    return render_template('archive/archive.html')


# TODO: Requires refactoring once archive plugin is refactored
# register_plugin(archive, menu='Archive')
