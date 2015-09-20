from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, register_js, Blueprint, register_menu

history = Blueprint('history', __name__)
register_plugin(history)

history.register_angular_route(
    '',
    url=history.url_prefix,
    template_url='history.html',
    controller='HistoryCtrl',
)

register_js('history', 'js/history.js', bp=history)

register_menu(history.url_prefix, 'History', icon='fa fa-history')
