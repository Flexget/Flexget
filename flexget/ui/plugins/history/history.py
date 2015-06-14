from __future__ import unicode_literals, division, absolute_import
import logging
from sqlalchemy import desc
from flexget.ui import register_plugin, menu
from flask import render_template, Blueprint
from flexget.plugin import DependencyError

try:
    from flexget.plugins.output.history import History
except ImportError:
    raise DependencyError(issued_by='ui.history', missing='history')

log = logging.getLogger('ui.history')
history = Blueprint('history', __name__)


@history.route('/')
@menu.register_menu(history, '.history', 'History', order=80)
def index():
    context = {'items': db_session.query(History).order_by(desc(History.time)).limit(50).all()}
    return render_template('history/history.html', **context)

register_plugin(history)
